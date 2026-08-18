"""Preserve append-only property-expense revisions and removals."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_property_expense_history"
down_revision: str | None = "0015_unique_tax_profile_dates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("property_expenses", sa.Column("replaces_id", sa.Uuid()))
    op.add_column("property_expenses", sa.Column("superseded_at", sa.DateTime(timezone=True)))
    op.add_column("property_expenses", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_property_expenses_replaces_id",
        "property_expenses",
        "property_expenses",
        ["replaces_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_property_expenses_replaces_id", "property_expenses", ["replaces_id"])
    op.create_index("ix_property_expenses_superseded_at", "property_expenses", ["superseded_at"])
    op.create_index("ix_property_expenses_deleted_at", "property_expenses", ["deleted_at"])


def downgrade() -> None:
    # Older code cannot distinguish active rows from revisions or tombstones.
    # Preserve only records it can safely interpret.
    op.execute(
        sa.text(
            "DELETE FROM property_expenses "
            "WHERE superseded_at IS NOT NULL OR deleted_at IS NOT NULL"
        )
    )
    op.drop_index("ix_property_expenses_deleted_at", table_name="property_expenses")
    op.drop_index("ix_property_expenses_superseded_at", table_name="property_expenses")
    op.drop_index("ix_property_expenses_replaces_id", table_name="property_expenses")
    op.drop_constraint("fk_property_expenses_replaces_id", "property_expenses", type_="foreignkey")
    op.drop_column("property_expenses", "deleted_at")
    op.drop_column("property_expenses", "superseded_at")
    op.drop_column("property_expenses", "replaces_id")
