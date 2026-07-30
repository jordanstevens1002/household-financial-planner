"""Exercise the local-account migration against the CI PostgreSQL database."""

import asyncio
import uuid

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings

LEGACY_SUBJECT = "migration-check-legacy-user"


async def seed_legacy_user() -> uuid.UUID:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        existing = await connection.scalar(
            text("SELECT id FROM application_users WHERE oidc_subject = :subject"),
            {"subject": LEGACY_SUBJECT},
        )
        if existing is not None:
            user_id = existing
        else:
            user_id = uuid.uuid4()
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
    return user_id


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


async def verify_downgrade(user_id: uuid.UUID) -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        subject = await connection.scalar(
            text("SELECT oidc_subject FROM application_users WHERE id = :id"),
            {"id": user_id},
        )
    await engine.dispose()
    assert subject == LEGACY_SUBJECT


def main() -> None:
    alembic = Config("alembic.ini")
    command.downgrade(alembic, "0011_loan_repayment_payers")
    user_id = asyncio.run(seed_legacy_user())
    command.upgrade(alembic, "head")
    asyncio.run(verify_upgrade(user_id))
    command.downgrade(alembic, "0011_loan_repayment_payers")
    asyncio.run(verify_downgrade(user_id))
    command.upgrade(alembic, "head")


if __name__ == "__main__":
    main()
