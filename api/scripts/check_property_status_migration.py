"""Rehearse repair of stale bundled property-status reference data."""

import asyncio
import uuid

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings

CUSTOM_CODE = "MIGRATION_CHECK_CUSTOM_STATUS"


async def create_stale_state() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE lookup_items SET generates_rental_income = NULL, "
                "applies_vacancy = NULL, applies_management_fee = NULL, "
                "applies_rental_expenses = NULL, is_occupied_by_household = NULL, "
                "is_active_asset = NULL WHERE category = 'property_status' "
                "AND code IN ('RENTED', 'PARTIALLY_RENTED', 'SHORT_TERM_RENTAL')"
            )
        )
        await connection.execute(
            text("DELETE FROM lookup_items WHERE category = 'property_status' AND code = :code"),
            {"code": CUSTOM_CODE},
        )
        await connection.execute(
            text(
                "INSERT INTO lookup_items "
                "(id, category, code, display_name, is_active, generates_rental_income, "
                "applies_vacancy, applies_management_fee, applies_rental_expenses, "
                "is_occupied_by_household, is_active_asset) VALUES "
                "(:id, 'property_status', :code, 'Custom migration check', true, "
                "true, false, false, false, true, true)"
            ),
            {"id": uuid.uuid4(), "code": CUSTOM_CODE},
        )
    await engine.dispose()


async def verify_and_clean_up() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT code, generates_rental_income, applies_vacancy, "
                    "applies_management_fee, applies_rental_expenses, "
                    "is_occupied_by_household, is_active_asset FROM lookup_items "
                    "WHERE category = 'property_status' AND code IN "
                    "('RENTED', 'PARTIALLY_RENTED', 'SHORT_TERM_RENTAL', :custom)"
                ),
                {"custom": CUSTOM_CODE},
            )
        ).mappings()
        statuses = {row["code"]: tuple(row.values())[1:] for row in rows}
        assert statuses["RENTED"] == (True, True, True, True, False, True)
        assert statuses["PARTIALLY_RENTED"] == (True, True, True, True, True, True)
        assert statuses["SHORT_TERM_RENTAL"] == (True, True, True, True, False, True)
        assert statuses[CUSTOM_CODE] == (True, False, False, False, True, True)
        await connection.execute(
            text("DELETE FROM lookup_items WHERE category = 'property_status' AND code = :code"),
            {"code": CUSTOM_CODE},
        )
    await engine.dispose()


def main() -> None:
    alembic = Config("alembic.ini")
    command.downgrade(alembic, "0016_property_expense_history")
    asyncio.run(create_stale_state())
    command.upgrade(alembic, "head")
    asyncio.run(verify_and_clean_up())


if __name__ == "__main__":
    main()
