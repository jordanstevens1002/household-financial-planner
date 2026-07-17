"""Create Phase 4 loan, goal, and loan-event structures."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_loans"
down_revision: str | None = "0003_event_timeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GOAL_TYPES = [
    "MAXIMUM_WEEKLY_REPAYMENT",
    "TARGET_LOAN_BALANCE",
    "TARGET_PAYOFF_DATE",
    "TARGET_PURCHASE_DATE",
    "TARGET_PURCHASE_PRICE",
    "EMERGENCY_FUND_MONTHS",
    "MAXIMUM_HOUSING_RATIO",
    "COMFORTABLE_HOUSING_RATIO",
    "TARGET_RETIREMENT_BALANCE",
    "TARGET_MONTHLY_SURPLUS",
    "CUSTOM_NUMERIC",
    "CUSTOM_DATE",
    "CUSTOM_BOOLEAN",
]

ADDITIONAL_LOAN_EVENT_TYPES = [
    "LOAN_REDRAWN",
    "LOAN_TERM_CHANGED",
    "LOAN_INTEREST_ONLY_STARTED",
    "LOAN_INTEREST_ONLY_ENDED",
]


def upgrade() -> None:
    interest_method = sa.Enum("DAILY", "MONTHLY", name="interest_calculation_method")
    repayment_frequency = sa.Enum("WEEKLY", "FORTNIGHTLY", "MONTHLY", name="repayment_frequency")
    op.create_table(
        "loan_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("property_id", sa.Uuid(), sa.ForeignKey("properties.id", ondelete="SET NULL")),
    )
    op.create_index("ix_loan_groups_household_id", "loan_groups", ["household_id"])
    op.create_index("ix_loan_groups_property_id", "loan_groups", ["property_id"])
    op.create_table(
        "loans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("property_id", sa.Uuid(), sa.ForeignKey("properties.id", ondelete="SET NULL")),
        sa.Column("loan_group_id", sa.Uuid(), sa.ForeignKey("loan_groups.id", ondelete="SET NULL")),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("lender", sa.String(200)),
        sa.Column("account_reference_masked", sa.String(50)),
        sa.Column("loan_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("original_balance", sa.Numeric(18, 2)),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("opening_balance_date", sa.Date(), nullable=False),
        sa.Column("initial_interest_rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("scheduled_repayment", sa.Numeric(18, 2)),
        sa.Column("term_months", sa.Integer()),
        sa.Column("interest_calculation_method", interest_method, nullable=False),
        sa.Column("repayment_frequency", repayment_frequency, nullable=False),
        sa.Column("is_interest_only", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("opening_balance >= 0"),
        sa.CheckConstraint("original_balance IS NULL OR original_balance >= 0"),
        sa.CheckConstraint("initial_interest_rate >= 0 AND initial_interest_rate <= 100"),
        sa.CheckConstraint("scheduled_repayment IS NULL OR scheduled_repayment >= 0"),
        sa.CheckConstraint("term_months IS NULL OR term_months > 0"),
    )
    for column in ("household_id", "property_id", "loan_group_id"):
        op.create_index(f"ix_loans_{column}", "loans", [column])
    op.add_column(
        "financial_events",
        sa.Column("loan_id", sa.Uuid(), sa.ForeignKey("loans.id", ondelete="CASCADE")),
    )
    op.create_index("ix_financial_events_loan_id", "financial_events", ["loan_id"])
    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="CASCADE")),
        sa.Column("property_id", sa.Uuid(), sa.ForeignKey("properties.id", ondelete="CASCADE")),
        sa.Column("loan_id", sa.Uuid(), sa.ForeignKey("loans.id", ondelete="CASCADE")),
        sa.Column("goal_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2)),
        sa.Column("target_percentage", sa.Numeric(7, 4)),
        sa.Column("target_date", sa.Date()),
        sa.Column("target_boolean", sa.Boolean()),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("target_amount IS NULL OR target_amount >= 0"),
        sa.CheckConstraint(
            "target_percentage IS NULL OR (target_percentage >= 0 AND target_percentage <= 100)"
        ),
    )
    op.create_index("ix_goals_household_id", "goals", ["household_id"])
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
                "category": "goal_type",
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "is_active": True,
            }
            for code in GOAL_TYPES
        ],
    )
    event_type = sa.table(
        "event_types",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("priority", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        event_type,
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "priority": 180 + index,
                "is_active": True,
            }
            for index, code in enumerate(ADDITIONAL_LOAN_EVENT_TYPES)
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    op.drop_table("goals")
    connection.execute(sa.text("DELETE FROM lookup_items WHERE category = 'goal_type'"))
    connection.execute(sa.text("DELETE FROM financial_events WHERE loan_id IS NOT NULL"))
    op.drop_index("ix_financial_events_loan_id", table_name="financial_events")
    op.drop_column("financial_events", "loan_id")
    event_type = sa.table("event_types", sa.column("code", sa.String()))
    connection.execute(
        sa.delete(event_type).where(event_type.c.code.in_(ADDITIONAL_LOAN_EVENT_TYPES))
    )
    op.drop_table("loans")
    op.drop_table("loan_groups")
    sa.Enum(name="repayment_frequency").drop(connection)
    sa.Enum(name="interest_calculation_method").drop(connection)
