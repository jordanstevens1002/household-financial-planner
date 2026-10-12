"""Add retirement account correction revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022_retirement_revisions"
down_revision: str | None = "0021_purchase_plan_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE lookup_items SET display_name = 'Australian superannuation' "
            "WHERE category = 'retirement_account_type' AND code = 'AUSTRALIAN_SUP'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE lookup_items SET display_name = 'Self-managed superannuation fund' "
            "WHERE category = 'retirement_account_type' AND code = 'SELF_MANAGED_SUP_FUND'"
        )
    )
    op.add_column(
        "retirement_accounts",
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_table(
        "retirement_account_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "retirement_account_id",
            sa.Uuid(),
            sa.ForeignKey("retirement_accounts.id", ondelete="CASCADE"),
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
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("previous_state", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")),
        sa.Column(
            "resulting_state",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("action IN ('CREATED', 'CORRECTED')"),
    )
    for column in ("retirement_account_id", "household_id", "actor_user_id"):
        op.create_index(
            f"ix_retirement_account_revisions_{column}", "retirement_account_revisions", [column]
        )
    op.create_index(
        "ix_retirement_account_revision_cursor",
        "retirement_account_revisions",
        ["retirement_account_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("retirement_account_revisions")
    op.drop_column("retirement_accounts", "revision")
    op.execute(
        sa.text(
            "UPDATE lookup_items SET display_name = 'Australian Sup' "
            "WHERE category = 'retirement_account_type' AND code = 'AUSTRALIAN_SUP'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE lookup_items SET display_name = 'Self Managed Sup Fund' "
            "WHERE category = 'retirement_account_type' AND code = 'SELF_MANAGED_SUP_FUND'"
        )
    )
