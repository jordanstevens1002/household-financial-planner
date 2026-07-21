"""Use country-neutral ownership terminology."""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_architecture_alignment"
down_revision: str | None = "0009_scenarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE owner_type RENAME VALUE 'SUPER_FUND' TO 'RETIREMENT_FUND'")
        return
    op.execute(
        "UPDATE property_ownership_interests "
        "SET owner_type = 'RETIREMENT_FUND' WHERE owner_type = 'SUPER_FUND'"
    )
    op.execute(
        "UPDATE purchase_ownership_allocations "
        "SET owner_type = 'RETIREMENT_FUND' WHERE owner_type = 'SUPER_FUND'"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE owner_type RENAME VALUE 'RETIREMENT_FUND' TO 'SUPER_FUND'")
        return
    op.execute(
        "UPDATE property_ownership_interests "
        "SET owner_type = 'SUPER_FUND' WHERE owner_type = 'RETIREMENT_FUND'"
    )
    op.execute(
        "UPDATE purchase_ownership_allocations "
        "SET owner_type = 'SUPER_FUND' WHERE owner_type = 'RETIREMENT_FUND'"
    )
