"""Local bootstrap and browser-session integration tests."""

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.sessions import utc_now
from app.core.auth import get_identity
from app.core.config import Settings, get_settings
from app.main import app
from app.models import ApplicationSession, ApplicationUser, GlobalRole

BOOTSTRAP_TOKEN = "test-bootstrap-token-that-is-long-enough"
PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "new correct horse battery staple"


def local_settings(**overrides: object) -> Settings:
    return Settings(
        local_auth_bootstrap_token=BOOTSTRAP_TOKEN,
        session_cookie_secure=False,
        **overrides,
    )


def configure(settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides.pop(get_identity, None)


async def bootstrap(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
        json={
            "username": "  Ａdministrator ",
            "password": PASSWORD,
            "display_name": "Local Administrator",
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_bootstrap_is_token_protected_and_permanently_closes(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    status_response = await client.get("/api/v1/auth/status")
    assert status_response.json() == {"bootstrap_required": True}

    rejected = await client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": "incorrect-bootstrap-token"},
        json={"username": "administrator", "password": PASSWORD},
    )
    assert rejected.status_code == 403

    payload = await bootstrap(client)
    assert payload["account"]["username"] == "administrator"  # type: ignore[index]
    assert payload["account"]["global_role"] == GlobalRole.ADMIN  # type: ignore[index]
    assert payload["csrf_token"]
    cookie = client.cookies.get("hfp_session")
    assert cookie
    user = await session.scalar(
        select(ApplicationUser).where(ApplicationUser.username == "administrator")
    )
    assert user is not None
    assert user.password_hash is not None
    assert PASSWORD not in user.password_hash

    assert (await client.get("/api/v1/auth/status")).json() == {"bootstrap_required": False}
    duplicate = await client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
        json={"username": "other-admin", "password": PASSWORD},
    )
    assert duplicate.status_code == 409


async def test_login_session_csrf_password_change_and_logout(
    client: AsyncClient,
) -> None:
    configure(local_settings())
    bootstrapped = await bootstrap(client)
    csrf = str(bootstrapped["csrf_token"])

    current = await client.get("/api/v1/auth/session")
    assert current.status_code == 200
    assert current.json()["account"]["username"] == "administrator"

    household_payload = {
        "display_name": "Cookie-authenticated household",
        "currency": "NZD",
        "jurisdiction": "NZ",
    }
    rejected_mutation = await client.post("/api/v1/households", json=household_payload)
    assert rejected_mutation.status_code == 403
    accepted_mutation = await client.post(
        "/api/v1/households",
        headers={"X-CSRF-Token": csrf},
        json=household_payload,
    )
    assert accepted_mutation.status_code == 201

    missing_csrf = await client.post(
        "/api/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert missing_csrf.status_code == 403

    changed = await client.post(
        "/api/v1/auth/password/change",
        headers={"X-CSRF-Token": csrf},
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200

    logged_out = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logged_out.status_code == 204
    assert (await client.get("/api/v1/auth/session")).status_code == 401

    old_password = await client.post(
        "/api/v1/auth/login",
        json={"username": "ADMINISTRATOR", "password": PASSWORD},
    )
    assert old_password.status_code == 401
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"username": "ADMINISTRATOR", "password": NEW_PASSWORD},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["csrf_token"]


async def test_failed_logins_are_rate_limited_with_retry_after(
    client: AsyncClient,
) -> None:
    configure(local_settings(login_max_attempts=2, login_block_minutes=1))
    await bootstrap(client)
    client.cookies.clear()

    for _ in range(2):
        failure = await client.post(
            "/api/v1/auth/login",
            json={"username": "administrator", "password": "wrong password value"},
        )
        assert failure.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"username": "administrator", "password": PASSWORD},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


async def test_idle_and_absolute_expiry_reject_sessions(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    record = await session.scalar(select(ApplicationSession))
    assert record is not None
    record.idle_expires_at = utc_now() - timedelta(seconds=1)
    await session.commit()

    expired = await client.get("/api/v1/auth/session")
    assert expired.status_code == 401
    assert expired.json()["detail"] == "Session expired or invalid"
