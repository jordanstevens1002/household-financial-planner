"""Repair bundled property-status calculation flags on existing databases."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_property_status_flags"
down_revision: str | None = "0016_property_expense_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# code: rental income, vacancy, management, rental expenses, household occupied, active asset
BUNDLED_PROPERTY_STATUSES = {
    "PLANNED": (False, False, False, False, False, False),
    "UNDER_CONTRACT": (False, False, False, False, False, False),
    "OWNER_OCCUPIED": (False, False, False, False, True, True),
    "RENTED": (True, True, True, True, False, True),
    "FAMILY_OCCUPIED": (False, False, False, False, False, True),
    "PARTIALLY_RENTED": (True, True, True, True, True, True),
    "SHORT_TERM_RENTAL": (True, True, True, True, False, True),
    "VACANT": (False, False, False, True, False, True),
    "RENOVATING": (False, False, False, True, False, True),
    "CONSTRUCTION": (False, False, False, True, False, True),
    "SOLD": (False, False, False, False, False, False),
    "TRANSFERRED": (False, False, False, False, False, False),
    "ARCHIVED": (False, False, False, False, False, False),
}


def upgrade() -> None:
    lookup_items = sa.table(
        "lookup_items",
        sa.column("category", sa.String()),
        sa.column("code", sa.String()),
        sa.column("generates_rental_income", sa.Boolean()),
        sa.column("applies_vacancy", sa.Boolean()),
        sa.column("applies_management_fee", sa.Boolean()),
        sa.column("applies_rental_expenses", sa.Boolean()),
        sa.column("is_occupied_by_household", sa.Boolean()),
        sa.column("is_active_asset", sa.Boolean()),
    )
    for code, flags in BUNDLED_PROPERTY_STATUSES.items():
        rent, vacancy, management, expenses, occupied, active = flags
        op.execute(
            lookup_items.update()
            .where(lookup_items.c.category == "property_status")
            .where(lookup_items.c.code == code)
            .values(
                generates_rental_income=rent,
                applies_vacancy=vacancy,
                applies_management_fee=management,
                applies_rental_expenses=expenses,
                is_occupied_by_household=occupied,
                is_active_asset=active,
            )
        )


def downgrade() -> None:
    # These values are canonical reference data rather than a schema feature.
    # Retaining them keeps older application versions functional and avoids
    # replacing valid values with the stale NULL state this migration repairs.
    pass
