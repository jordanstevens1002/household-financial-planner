"""Persist audited legacy identity migration reviews."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_legacy_migration_reviews"
down_revision: str | None = "0013_legacy_mapping_safety"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legacy_migration_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reviewed_by_application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "unresolved_identity_ids",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("accepted_login_loss", sa.Boolean(), nullable=False),
        sa.Column("migration_state_hash", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_legacy_migration_reviews_reviewed_by_application_user_id",
        "legacy_migration_reviews",
        ["reviewed_by_application_user_id"],
    )
    op.create_index(
        "ix_legacy_migration_reviews_migration_state_hash",
        "legacy_migration_reviews",
        ["migration_state_hash"],
    )


def downgrade() -> None:
    op.drop_table("legacy_migration_reviews")
