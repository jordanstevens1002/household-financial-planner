"""Create Phase 5 rental profile and property expense structures."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_rental_expenses"
down_revision: str | None = "0004_loans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPENSE_TYPES = [
    "COUNCIL_RATES",
    "WATER",
    "STRATA_OR_BODY_CORPORATE",
    "INSURANCE",
    "PROPERTY_MANAGEMENT",
    "REPAIRS_AND_MAINTENANCE",
    "LAND_TAX",
    "UTILITIES",
    "CLEANING",
    "GARDENING",
    "SPECIAL_LEVY",
    "OTHER",
]


def upgrade() -> None:
    op.alter_column(
        "lookup_items",
        "applies_landlord_expenses",
        new_column_name="applies_rental_expenses",
    )
    frequency = sa.Enum(
        "WEEKLY",
        "FORTNIGHTLY",
        "MONTHLY",
        "QUARTERLY",
        "ANNUAL",
        "ONCE",
        name="payment_frequency",
    )
    op.create_table(
        "rental_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Uuid(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("market_rent_amount", sa.Numeric(18, 2)),
        sa.Column("charged_rent_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("frequency", frequency, nullable=False),
        sa.Column("vacancy_rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("management_fee_rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("letting_fee", sa.Numeric(18, 2)),
        sa.Column("rental_share_percentage", sa.Numeric(7, 4), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
        sa.CheckConstraint("market_rent_amount IS NULL OR market_rent_amount >= 0"),
        sa.CheckConstraint("charged_rent_amount >= 0"),
        sa.CheckConstraint("vacancy_rate >= 0 AND vacancy_rate <= 100"),
        sa.CheckConstraint("management_fee_rate >= 0 AND management_fee_rate <= 100"),
        sa.CheckConstraint("letting_fee IS NULL OR letting_fee >= 0"),
        sa.CheckConstraint("rental_share_percentage > 0 AND rental_share_percentage <= 100"),
    )
    op.create_index("ix_rental_profiles_property_id", "rental_profiles", ["property_id"])
    op.create_index("ix_rental_profiles_effective_from", "rental_profiles", ["effective_from"])
    op.create_table(
        "property_expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Uuid(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expense_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "frequency",
            sa.Enum(name="payment_frequency", create_type=False),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("is_rental_expense", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
        sa.CheckConstraint("amount >= 0"),
    )
    op.create_index("ix_property_expenses_property_id", "property_expenses", ["property_id"])
    op.create_index("ix_property_expenses_effective_from", "property_expenses", ["effective_from"])
    lookup = sa.table(
        "lookup_items",
        sa.column("id", sa.Uuid()),
        sa.column("category", sa.String()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        lookup,
        [
            {
                "id": uuid.uuid4(),
                "category": "property_expense_type",
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "is_active": True,
            }
            for code in EXPENSE_TYPES
        ],
    )


def downgrade() -> None:
    # Pre-v1.0 migrations are forward-only; this is a best-effort development convenience.
    connection = op.get_bind()
    op.drop_table("property_expenses")
    op.drop_table("rental_profiles")
    connection.execute(sa.text("DELETE FROM lookup_items WHERE category = 'property_expense_type'"))
    sa.Enum(name="payment_frequency").drop(connection)
    op.alter_column(
        "lookup_items",
        "applies_rental_expenses",
        new_column_name="applies_landlord_expenses",
    )
