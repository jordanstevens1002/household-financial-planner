"""Add ordinary named borrowers to loans."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_loan_borrowers"
down_revision: str | None = "0018_loan_group_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loan_borrowers",
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
            sa.ForeignKey("people.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("loan_id", "person_id"),
    )
    op.create_index("ix_loan_borrowers_loan_id", "loan_borrowers", ["loan_id"])
    op.create_index("ix_loan_borrowers_person_id", "loan_borrowers", ["person_id"])


def downgrade() -> None:
    op.drop_table("loan_borrowers")
