"""Global local-account administration integration tests."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.accounts.passwords import verify_password
from app.accounts.recovery import recover_local_admin
from app.accounts.sessions import as_utc, utc_now
from app.accounts.tokens import hash_token
from app.core.database import Base, get_session
from app.main import app
from app.models import (
    ApplicationSession,
    ApplicationUser,
    Household,
    HouseholdMembership,
    HouseholdRole,
    PasswordResetToken,
)

from .test_auth_api import bootstrap, configure, local_settings


async def create_local_user(client: AsyncClient, username: str = "new-person") -> dict:
    response = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"username": username, "display_name": "New Person"},
    )
    assert response.status_code == 201
    return response.json()


async def test_admin_can_list_and_create_local_users_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    created = await create_local_user(client)
    assert created["account"]["username"] == "new-person"
    assert created["account"]["global_role"] == "USER"
    assert created["account"]["must_change_password"] is True
    temporary_password = created["temporary_password"]

    stored = await session.scalar(
        select(ApplicationUser).where(ApplicationUser.username == "new-person")
    )
    assert stored is not None and stored.password_hash is not None
    assert temporary_password not in stored.password_hash
    assert verify_password(stored.password_hash, temporary_password)
    assert stored.password_expires_at is not None
    remaining = as_utc(stored.password_expires_at) - utc_now()
    assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)

    listed = await client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    assert [item["username"] for item in listed.json()] == ["administrator", "new-person"]
    assert "temporary_password" not in listed.text
    assert "password_hash" not in listed.text


async def test_final_active_admin_is_protected_and_disabled_sessions_are_revoked(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    bootstrapped = await bootstrap(client)
    admin_id = bootstrapped["account"]["id"]
    csrf = client.cookies["hfp_csrf"]
    for patch in ({"global_role": "USER"}, {"is_active": False}):
        response = await client.patch(
            f"/api/v1/admin/users/{admin_id}",
            headers={"X-CSRF-Token": csrf},
            json=patch,
        )
        assert response.status_code == 409
        assert "confirm_self_lockout" in response.json()["detail"]

    created = await create_local_user(client, "second-admin")
    second_id = created["account"]["id"]
    promoted = await client.patch(
        f"/api/v1/admin/users/{second_id}",
        headers={"X-CSRF-Token": csrf},
        json={"global_role": "ADMIN"},
    )
    assert promoted.status_code == 200
    disabled = await client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers={"X-CSRF-Token": csrf},
        json={"is_active": False, "confirm_self_lockout": True},
    )
    assert disabled.status_code == 409
    assert disabled.json()["detail"] == "Another recovery-capable administrator is required"

    second = await session.get(ApplicationUser, uuid.UUID(second_id))
    assert second is not None
    second.must_change_password = False
    second.password_expires_at = utc_now() - timedelta(seconds=1)
    await session.commit()
    expired_rejected = await client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers={"X-CSRF-Token": csrf},
        json={"is_active": False, "confirm_self_lockout": True},
    )
    assert expired_rejected.status_code == 409
    assert expired_rejected.json()["detail"] == "Another recovery-capable administrator is required"

    second.password_expires_at = None
    await session.commit()
    disabled = await client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers={"X-CSRF-Token": csrf},
        json={"is_active": False, "confirm_self_lockout": True},
    )
    assert disabled.status_code == 200
    assert not (
        await session.scalars(
            select(ApplicationSession).where(
                ApplicationSession.application_user_id == uuid.UUID(admin_id)
            )
        )
    ).all()


async def test_household_owner_is_not_a_global_administrator(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    created = await create_local_user(client, "household-owner")
    user = await session.get(ApplicationUser, uuid.UUID(created["account"]["id"]))
    assert user is not None
    household = Household(display_name="Private", currency="NZD", jurisdiction="NZ")
    session.add(household)
    await session.flush()
    session.add(
        HouseholdMembership(
            household_id=household.id,
            application_user_id=user.id,
            role=HouseholdRole.OWNER,
        )
    )
    user.password_hash = user.password_hash
    await session.commit()

    client.cookies.clear()
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "household-owner",
            "password": created["temporary_password"],
        },
    )
    assert logged_in.status_code == 200
    changed = await client.post(
        "/api/v1/auth/password/change",
        headers={"X-CSRF-Token": logged_in.json()["csrf_token"]},
        json={
            "current_password": created["temporary_password"],
            "new_password": "owner-password",
        },
    )
    assert changed.status_code == 200
    # Household ownership remains independent of the global account role.
    assert (await client.get("/api/v1/admin/users")).status_code == 403


async def test_reset_link_is_single_use_and_invalidates_sessions(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    created = await create_local_user(client, "reset-person")
    user_id = created["account"]["id"]
    user_uuid = uuid.UUID(user_id)
    now = utc_now()
    session.add(
        ApplicationSession(
            application_user_id=user_uuid,
            session_token_hash=hash_token("session-to-revoke"),
            csrf_token_hash=hash_token("csrf-to-revoke"),
            last_seen_at=now,
            idle_expires_at=now + timedelta(minutes=60),
            absolute_expires_at=now + timedelta(hours=12),
        )
    )
    await session.commit()
    reset = await client.post(
        f"/api/v1/admin/users/{user_id}/password-reset",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
    )
    assert reset.status_code == 200
    assert not (
        await session.scalars(
            select(ApplicationSession).where(ApplicationSession.application_user_id == user_uuid)
        )
    ).all()
    raw_token = reset.json()["reset_path"].split("token=", 1)[1]
    stored = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.application_user_id == user_uuid)
    )
    assert stored is not None
    assert stored.token_hash == hash_token(raw_token)
    assert raw_token != stored.token_hash
    remaining = as_utc(stored.expires_at) - utc_now()
    assert timedelta(minutes=29, seconds=59) < remaining <= timedelta(minutes=30)

    client.cookies.clear()
    completed = await client.post(
        "/api/v1/auth/password/reset",
        json={"token": raw_token, "new_password": "new-password"},
    )
    assert completed.status_code == 204
    reused = await client.post(
        "/api/v1/auth/password/reset",
        json={"token": raw_token, "new_password": "another-password"},
    )
    assert reused.status_code == 400

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "reset-person", "password": "new-password"},
    )
    assert login.status_code == 200
    assert login.json()["account"]["must_change_password"] is False


async def test_account_audit_logs_do_not_contain_returned_secrets(
    client: AsyncClient, caplog
) -> None:
    configure(local_settings())
    await bootstrap(client)
    with caplog.at_level(logging.INFO):
        created = await create_local_user(client, "audited-person")
        await client.post(
            f"/api/v1/admin/users/{created['account']['id']}/password-reset",
            headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        )
    text = caplog.text
    assert "admin_user_created" in text
    assert "admin_password_reset_issued" in text
    assert created["account"]["id"] in text
    assert created["temporary_password"] not in text


async def test_reset_token_is_consumed_by_exactly_one_concurrent_request(
    tmp_path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reset-race.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    raw_token = "one-reset-token-for-two-concurrent-requests"
    async with factory() as database:
        user = ApplicationUser(
            username="race-user",
            password_hash="replaced-before-verification",
        )
        database.add(user)
        await database.flush()
        database.add(
            PasswordResetToken(
                application_user_id=user.id,
                token_hash=hash_token(raw_token),
                expires_at=utc_now() + timedelta(minutes=30),
            )
        )
        await database.commit()
        user_id = user.id

    async def independent_session() -> AsyncIterator[AsyncSession]:
        async with factory() as database:
            yield database

    app.dependency_overrides[get_session] = independent_session
    try:
        async with (
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as first,
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as second,
        ):
            responses = await asyncio.gather(
                first.post(
                    "/api/v1/auth/password/reset",
                    json={"token": raw_token, "new_password": "first-password"},
                ),
                second.post(
                    "/api/v1/auth/password/reset",
                    json={"token": raw_token, "new_password": "second-password"},
                ),
            )
        assert sorted(response.status_code for response in responses) == [204, 400]
        async with factory() as database:
            stored = await database.get(ApplicationUser, user_id)
            assert stored is not None and stored.password_hash is not None
            matching = [
                candidate
                for candidate in ("first-password", "second-password")
                if verify_password(stored.password_hash, candidate)
            ]
            assert len(matching) == 1
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def test_operator_recovery_restores_admin_and_invalidates_credentials(
    client: AsyncClient,
    session: AsyncSession,
    caplog,
) -> None:
    configure(local_settings())
    await bootstrap(client)
    created = await create_local_user(client, "recovery-user")
    user_id = uuid.UUID(created["account"]["id"])
    now = utc_now()
    session.add(
        ApplicationSession(
            application_user_id=user_id,
            session_token_hash=hash_token("recovery-session"),
            csrf_token_hash=hash_token("recovery-csrf"),
            last_seen_at=now,
            idle_expires_at=now + timedelta(minutes=60),
            absolute_expires_at=now + timedelta(hours=12),
        )
    )
    session.add(
        PasswordResetToken(
            application_user_id=user_id,
            token_hash=hash_token("recovery-reset-token"),
            expires_at=now + timedelta(minutes=30),
        )
    )
    await session.commit()

    password = "offline-recovery-password"
    with caplog.at_level(logging.WARNING):
        recovered = await recover_local_admin(session, "recovery-user", password, local_settings())
    assert recovered.global_role == "ADMIN"
    assert recovered.is_active is True
    assert recovered.must_change_password is True
    assert recovered.password_hash is not None
    assert verify_password(recovered.password_hash, password)
    assert not (
        await session.scalars(
            select(ApplicationSession).where(ApplicationSession.application_user_id == user_id)
        )
    ).all()
    assert not (
        await session.scalars(
            select(PasswordResetToken).where(PasswordResetToken.application_user_id == user_id)
        )
    ).all()
    assert "operator_admin_recovery_completed" in caplog.text
    assert password not in caplog.text
