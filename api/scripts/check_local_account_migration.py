"""Exercise the local-account migration against the CI PostgreSQL database."""

import asyncio
import uuid

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings

LEGACY_SUBJECT = "migration-check-legacy-user"
LOCAL_USERNAME = "migration-check-local-user"


def downgraded_local_subject(user_id: uuid.UUID) -> str:
    return f"local-account:{user_id}"


async def seed_legacy_user() -> tuple[uuid.UUID, bool]:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        existing = await connection.scalar(
            text("SELECT id FROM application_users WHERE oidc_subject = :subject"),
            {"subject": LEGACY_SUBJECT},
        )
        if existing is not None:
            user_id = existing
            created = False
        else:
            user_id = uuid.uuid4()
            created = True
            await connection.execute(
                text(
                    "INSERT INTO application_users "
                    "(id, oidc_subject, email, display_name) "
                    "VALUES (:id, :subject, :email, :display_name)"
                ),
                {
                    "id": user_id,
                    "subject": LEGACY_SUBJECT,
                    "email": "migration-check@example.invalid",
                    "display_name": "Migration Check",
                },
            )
    await engine.dispose()
    return user_id, created


async def verify_upgrade(user_id: uuid.UUID) -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        identity = (
            await connection.execute(
                text(
                    "SELECT source_application_user_id, oidc_subject "
                    "FROM legacy_identities WHERE oidc_subject = :subject"
                ),
                {"subject": LEGACY_SUBJECT},
            )
        ).one()
        account = (
            await connection.execute(
                text(
                    "SELECT global_role, is_active, must_change_password "
                    "FROM application_users WHERE id = :id"
                ),
                {"id": user_id},
            )
        ).one()

    await engine.dispose()
    assert identity.source_application_user_id == user_id
    assert identity.oidc_subject == LEGACY_SUBJECT
    assert account.global_role == "USER"
    assert account.is_active is True
    assert account.must_change_password is False


async def seed_local_user() -> uuid.UUID:
    user_id = uuid.uuid4()
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO application_users "
                "(id, oidc_subject, username, global_role, is_active, "
                "must_change_password) "
                "VALUES (:id, NULL, :username, 'USER', true, false)"
            ),
            {"id": user_id, "username": LOCAL_USERNAME},
        )
    await engine.dispose()
    return user_id


async def seed_mapping_history(legacy_user_id: uuid.UUID, local_user_id: uuid.UUID) -> None:
    """Ensure the safety migration permits audited remapping before downgrade."""
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        identity_id = await connection.scalar(
            text(
                "SELECT id FROM legacy_identities "
                "WHERE source_application_user_id = :legacy_user_id"
            ),
            {"legacy_user_id": legacy_user_id},
        )
        assert identity_id is not None
        await connection.execute(
            text(
                "INSERT INTO legacy_identity_mappings "
                "(id, legacy_identity_id, application_user_id, "
                "mapped_by_application_user_id, revoked_at, "
                "revoked_by_application_user_id) VALUES "
                "(:revoked_id, :identity_id, :local_user_id, :local_user_id, now(), "
                ":local_user_id), "
                "(:active_id, :identity_id, :local_user_id, :local_user_id, NULL, NULL)"
            ),
            {
                "revoked_id": uuid.uuid4(),
                "active_id": uuid.uuid4(),
                "identity_id": identity_id,
                "local_user_id": local_user_id,
            },
        )
    await engine.dispose()


async def verify_downgrade(
    legacy_user_id: uuid.UUID,
    local_user_id: uuid.UUID,
) -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        legacy_subject = await connection.scalar(
            text("SELECT oidc_subject FROM application_users WHERE id = :id"),
            {"id": legacy_user_id},
        )
        local_subject = await connection.scalar(
            text("SELECT oidc_subject FROM application_users WHERE id = :id"),
            {"id": local_user_id},
        )
    await engine.dispose()
    assert legacy_subject == LEGACY_SUBJECT
    assert local_subject == downgraded_local_subject(local_user_id)


async def remove_check_user(user_id: uuid.UUID) -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM application_users WHERE id = :id"),
            {"id": user_id},
        )
    await engine.dispose()


async def verify_reupgrade(local_user_id: uuid.UUID) -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        account = (
            await connection.execute(
                text("SELECT oidc_subject, username FROM application_users WHERE id = :id"),
                {"id": local_user_id},
            )
        ).one()
        identity_subject = await connection.scalar(
            text(
                "SELECT oidc_subject FROM legacy_identities WHERE source_application_user_id = :id"
            ),
            {"id": local_user_id},
        )
    await engine.dispose()
    expected_subject = downgraded_local_subject(local_user_id)
    assert account.oidc_subject == expected_subject
    assert account.username is None
    assert identity_subject == expected_subject


def main() -> None:
    alembic = Config("alembic.ini")
    command.downgrade(alembic, "0011_loan_repayment_payers")
    user_id, created = asyncio.run(seed_legacy_user())
    command.upgrade(alembic, "head")
    asyncio.run(verify_upgrade(user_id))
    local_user_id = asyncio.run(seed_local_user())
    asyncio.run(seed_mapping_history(user_id, local_user_id))
    command.downgrade(alembic, "0011_loan_repayment_payers")
    asyncio.run(verify_downgrade(user_id, local_user_id))
    command.upgrade(alembic, "head")
    asyncio.run(verify_reupgrade(local_user_id))
    asyncio.run(remove_check_user(local_user_id))
    if created:
        asyncio.run(remove_check_user(user_id))


if __name__ == "__main__":
    main()
