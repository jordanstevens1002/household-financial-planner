"""Add recoverable purchase-plan child records and revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_purchase_plan_details"
down_revision: str | None = "0020_repayment_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in (
        "purchase_funding_sources",
        "purchase_costs",
        "purchase_ownership_allocations",
    ):
        op.add_column(
            table,
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        )
        op.add_column(
            table,
            sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        )
    op.create_table(
        "purchase_plan_child_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_plan_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("child_type", sa.String(20), nullable=False),
        sa.Column("child_id", sa.Uuid()),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column(
            "previous_state",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        ),
        sa.Column(
            "resulting_state",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("child_type IN ('FUNDING', 'COST', 'OWNERSHIP')"),
        sa.CheckConstraint("action IN ('CREATED', 'CORRECTED', 'RETIRED', 'REPLACED')"),
    )
    op.create_index(
        "ix_purchase_plan_child_revisions_purchase_plan_id",
        "purchase_plan_child_revisions",
        ["purchase_plan_id"],
    )
    op.create_index(
        "ix_purchase_plan_child_revisions_actor_user_id",
        "purchase_plan_child_revisions",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_purchase_plan_child_revisions_household_id",
        "purchase_plan_child_revisions",
        ["household_id"],
    )
    op.create_index(
        "ix_purchase_child_revision_plan_cursor",
        "purchase_plan_child_revisions",
        ["purchase_plan_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("purchase_plan_child_revisions")
    for table in (
        "purchase_ownership_allocations",
        "purchase_costs",
        "purchase_funding_sources",
    ):
        op.drop_column(table, "revision")
        op.drop_column(table, "is_active")
