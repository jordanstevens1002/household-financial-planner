"""Create Phase 3 event and timeline tables."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_event_timeline"
down_revision: str | None = "0002_property_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


EVENT_TYPES = [
    "HOUSEHOLD_MEMBER_ADDED",
    "HOUSEHOLD_MEMBER_REMOVED",
    "INCOME_STARTED",
    "INCOME_CHANGED",
    "INCOME_ENDED",
    "PROPERTY_PURCHASED",
    "PROPERTY_STATUS_CHANGED",
    "PROPERTY_VALUED",
    "PROPERTY_SOLD",
    "PROPERTY_TRANSFERRED",
    "OWNERSHIP_CHANGED",
    "RENT_STARTED",
    "RENT_CHANGED",
    "RENT_ENDED",
    "PROPERTY_EXPENSE_CHANGED",
    "SPECIAL_LEVY",
    "LOAN_OPENED",
    "LOAN_RATE_CHANGED",
    "LOAN_REPAYMENT_CHANGED",
    "LOAN_REFINANCED",
    "LOAN_LUMP_SUM_PAID",
    "LOAN_OFFSET_CHANGED",
    "LOAN_CLOSED",
    "RETIREMENT_BALANCE_ADJUSTED",
    "RETIREMENT_CONTRIBUTION_CHANGED",
    "HOUSEHOLD_EXPENSE_CHANGED",
    "ASSET_VALUE_CHANGED",
    "LIABILITY_CHANGED",
    "CUSTOM_EVENT",
]


def upgrade() -> None:
    classification = sa.Enum("OBSERVED", "PLANNED", "PROJECTED", name="event_classification")
    op.create_table(
        "event_types",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_event_types_code", "event_types", ["code"], unique=True)
    event_types = sa.table(
        "event_types",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("priority", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        event_types,
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "priority": (index + 1) * 10,
                "is_active": True,
            }
            for index, code in enumerate(EVENT_TYPES)
        ],
    )
    op.create_table(
        "financial_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type_id", sa.Uuid(), sa.ForeignKey("event_types.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100)),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("property_id", sa.Uuid(), sa.ForeignKey("properties.id", ondelete="CASCADE")),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="CASCADE")),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("percentage", sa.Numeric(7, 4)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column("classification", classification, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("data_quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("percentage IS NULL OR (percentage >= 0 AND percentage <= 100)"),
        sa.UniqueConstraint("household_id", "idempotency_key"),
    )
    for column in (
        "household_id",
        "event_type_id",
        "effective_at",
        "property_id",
        "person_id",
    ):
        op.create_index(f"ix_financial_events_{column}", "financial_events", [column])


def downgrade() -> None:
    op.drop_table("financial_events")
    op.drop_table("event_types")
    sa.Enum(name="event_classification").drop(op.get_bind())
