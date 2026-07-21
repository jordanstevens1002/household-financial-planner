"""Create Phase 7 retirement account and projection structures."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_retirement_accounts"
down_revision: str | None = "0006_income_tax_cashflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retirement_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL")),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("account_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("opening_balance_date", sa.Date(), nullable=False),
        sa.Column("expected_return_rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("annual_fees", sa.Numeric(18, 2), nullable=False),
        sa.Column("retirement_age", sa.Integer()),
        sa.Column("provider_code", sa.String(80)),
        sa.Column("provider_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("opening_balance >= 0"),
        sa.CheckConstraint("expected_return_rate >= -100 AND expected_return_rate <= 100"),
        sa.CheckConstraint("annual_fees >= 0"),
        sa.CheckConstraint(
            "retirement_age IS NULL OR (retirement_age >= 0 AND retirement_age <= 120)"
        ),
    )
    op.create_index("ix_retirement_accounts_household_id", "retirement_accounts", ["household_id"])
    op.create_index("ix_retirement_accounts_person_id", "retirement_accounts", ["person_id"])
    op.create_table(
        "retirement_contribution_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "retirement_account_id",
            sa.Uuid(),
            sa.ForeignKey("retirement_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("employer_rate", sa.Numeric(7, 4)),
        sa.Column("employer_amount", sa.Numeric(18, 2)),
        sa.Column("voluntary_pre_tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("voluntary_post_tax_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("contribution_tax_rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("annual_pre_tax_cap", sa.Numeric(18, 2)),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
        sa.CheckConstraint(
            "employer_rate IS NULL OR (employer_rate >= 0 AND employer_rate <= 100)"
        ),
        sa.CheckConstraint("employer_amount IS NULL OR employer_amount >= 0"),
        sa.CheckConstraint("voluntary_pre_tax_amount >= 0"),
        sa.CheckConstraint("voluntary_post_tax_amount >= 0"),
        sa.CheckConstraint("contribution_tax_rate >= 0 AND contribution_tax_rate <= 100"),
        sa.CheckConstraint("annual_pre_tax_cap IS NULL OR annual_pre_tax_cap >= 0"),
    )
    op.create_index(
        "ix_retirement_contribution_profiles_retirement_account_id",
        "retirement_contribution_profiles",
        ["retirement_account_id"],
    )
    op.create_index(
        "ix_retirement_contribution_profiles_effective_from",
        "retirement_contribution_profiles",
        ["effective_from"],
    )
    event_enum = sa.Enum("BALANCE_ADJUSTMENT", name="retirement_event_type")
    op.create_table(
        "retirement_account_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "retirement_account_id",
            sa.Uuid(),
            sa.ForeignKey("retirement_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", event_enum, nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(100)),
        sa.Column("notes", sa.String(2000)),
        sa.UniqueConstraint("retirement_account_id", "idempotency_key"),
    )
    op.create_index(
        "ix_retirement_account_events_retirement_account_id",
        "retirement_account_events",
        ["retirement_account_id"],
    )
    op.create_index(
        "ix_retirement_account_events_effective_date",
        "retirement_account_events",
        ["effective_date"],
    )


def downgrade() -> None:
    # Pre-v1.0 migrations are forward-only; this is a best-effort development convenience.
    op.drop_table("retirement_account_events")
    op.drop_table("retirement_contribution_profiles")
    op.drop_table("retirement_accounts")
