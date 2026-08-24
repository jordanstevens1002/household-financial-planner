"""Repair legacy loan-group assignments and catalogue names."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "0018_loan_group_integrity"
down_revision: str | None = "0017_property_status_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def repair_loan_groups(connection: Connection) -> None:
    """Normalize names, merge duplicates, and clear invalid legacy links."""
    groups = connection.execute(
        sa.text("SELECT id, household_id, property_id, display_name FROM loan_groups ORDER BY id")
    ).mappings()
    canonical_by_scope: dict[tuple[str, str, str], object] = {}
    for group in groups:
        normalized = " ".join(group["display_name"].split())
        if not normalized:
            normalized = f"Unnamed loan group {str(group['id'])[:8]}"
        key = (
            str(group["household_id"]),
            str(group["property_id"] or ""),
            normalized.casefold(),
        )
        canonical_id = canonical_by_scope.get(key)
        if canonical_id is None:
            canonical_by_scope[key] = group["id"]
            connection.execute(
                sa.text("UPDATE loan_groups SET display_name = :name WHERE id = :id"),
                {"id": group["id"], "name": normalized},
            )
            continue
        connection.execute(
            sa.text("UPDATE loans SET loan_group_id = :canonical WHERE loan_group_id = :duplicate"),
            {"canonical": canonical_id, "duplicate": group["id"]},
        )
        connection.execute(sa.text("DELETE FROM loan_groups WHERE id = :id"), {"id": group["id"]})

    connection.execute(
        sa.text(
            "UPDATE loans SET loan_group_id = NULL "
            "WHERE loan_group_id IS NOT NULL AND NOT EXISTS ("
            "SELECT 1 FROM loan_groups AS loan_group "
            "WHERE loan_group.id = loans.loan_group_id "
            "AND loan_group.household_id = loans.household_id "
            "AND (loan_group.property_id = loans.property_id "
            "OR (loan_group.property_id IS NULL AND loans.property_id IS NULL)))"
        )
    )


def upgrade() -> None:
    repair_loan_groups(op.get_bind())
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_loan_groups_scope_normalized_name "
            "ON loan_groups (household_id, "
            "COALESCE(property_id, '00000000-0000-0000-0000-000000000000'::uuid), "
            "lower(display_name))"
        )
    )


def downgrade() -> None:
    op.drop_index("uq_loan_groups_scope_normalized_name", table_name="loan_groups")
    # Cleaned names and invalid relationships cannot be reconstructed safely.
