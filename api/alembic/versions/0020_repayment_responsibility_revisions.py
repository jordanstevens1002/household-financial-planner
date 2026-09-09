"""Add durable repayment-responsibility allocation revisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020_repayment_revisions"
down_revision: str | None = "0019_loan_borrowers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loan_repayment_responsibility_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "loan_id",
            sa.Uuid(),
            sa.ForeignKey("loans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column(
            "previous_allocations",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "resulting_allocations",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("action IN ('CREATED', 'REPLACED', 'CLOSED')"),
    )
    op.create_index(
        "ix_loan_repayment_responsibility_revisions_loan_id",
        "loan_repayment_responsibility_revisions",
        ["loan_id"],
    )
    op.create_index(
        "ix_loan_repayment_responsibility_revisions_actor_user_id",
        "loan_repayment_responsibility_revisions",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_loan_repayment_responsibility_revisions_effective_from",
        "loan_repayment_responsibility_revisions",
        ["effective_from"],
    )
    op.create_index(
        "ix_loan_repayment_revision_cursor",
        "loan_repayment_responsibility_revisions",
        ["loan_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("loan_repayment_responsibility_revisions")
