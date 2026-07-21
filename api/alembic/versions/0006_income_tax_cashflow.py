"""Create Phase 6 income, tax profile, and household expense structures."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_income_tax_cashflow"
down_revision: str | None = "0005_rental_expenses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOUSEHOLD_EXPENSE_TYPES = [
    "HOUSING",
    "GROCERIES",
    "UTILITIES",
    "TRANSPORT",
    "INSURANCE",
    "HEALTH",
    "EDUCATION",
    "CHILDCARE",
    "PERSONAL",
    "ENTERTAINMENT",
    "TRAVEL",
    "DEBT_REPAYMENT",
    "SAVINGS",
    "OTHER",
]


def _frequency_column() -> sa.Enum:
    return sa.Enum(name="payment_frequency", create_type=False)


def upgrade() -> None:
    op.create_table(
        "income_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("income_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("frequency", _frequency_column(), nullable=False),
        sa.Column("salary_sacrifice_amount", sa.Numeric(18, 2)),
        sa.Column("annual_growth_rate", sa.Numeric(7, 4)),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("taxable", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("gross_amount >= 0"),
        sa.CheckConstraint("salary_sacrifice_amount IS NULL OR salary_sacrifice_amount >= 0"),
        sa.CheckConstraint(
            "annual_growth_rate IS NULL OR "
            "(annual_growth_rate >= -100 AND annual_growth_rate <= 100)"
        ),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    op.create_index("ix_income_sources_person_id", "income_sources", ["person_id"])
    op.create_index("ix_income_sources_effective_from", "income_sources", ["effective_from"])
    op.create_table(
        "person_tax_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("jurisdiction", sa.String(50), nullable=False),
        sa.Column("tax_year", sa.String(20), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    op.create_index("ix_person_tax_profiles_person_id", "person_tax_profiles", ["person_id"])
    op.create_index(
        "ix_person_tax_profiles_effective_from", "person_tax_profiles", ["effective_from"]
    )
    op.create_table(
        "household_expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="CASCADE")),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("frequency", _frequency_column(), nullable=False),
        sa.Column("annual_growth_rate", sa.Numeric(7, 4)),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("is_essential", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("amount >= 0"),
        sa.CheckConstraint(
            "annual_growth_rate IS NULL OR "
            "(annual_growth_rate >= -100 AND annual_growth_rate <= 100)"
        ),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    op.create_index("ix_household_expenses_household_id", "household_expenses", ["household_id"])
    op.create_index(
        "ix_household_expenses_effective_from", "household_expenses", ["effective_from"]
    )
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
                "category": "household_expense_type",
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "is_active": True,
            }
            for code in HOUSEHOLD_EXPENSE_TYPES
        ],
    )


def downgrade() -> None:
    # Pre-v1.0 migrations are forward-only; this is a best-effort development convenience.
    connection = op.get_bind()
    op.drop_table("household_expenses")
    op.drop_table("person_tax_profiles")
    op.drop_table("income_sources")
    connection.execute(
        sa.text("DELETE FROM lookup_items WHERE category = 'household_expense_type'")
    )
