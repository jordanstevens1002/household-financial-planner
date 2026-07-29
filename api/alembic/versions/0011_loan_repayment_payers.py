"""Add optional dated loan repayment responsibility allocations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_loan_repayment_payers"
down_revision: str | None = "0010_architecture_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loan_repayment_responsibilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "loan_id",
            sa.Uuid(),
            sa.ForeignKey("loans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("responsibility_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("responsibility_percentage > 0 AND responsibility_percentage <= 100"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    op.create_index(
        "ix_loan_repayment_responsibilities_loan_id",
        "loan_repayment_responsibilities",
        ["loan_id"],
    )
    op.create_index(
        "ix_loan_repayment_responsibilities_person_id",
        "loan_repayment_responsibilities",
        ["person_id"],
    )
    op.create_index(
        "ix_loan_repayment_responsibilities_effective_from",
        "loan_repayment_responsibilities",
        ["effective_from"],
    )


def downgrade() -> None:
    op.drop_table("loan_repayment_responsibilities")
