"""Add auditable mapping revocation and membership reconciliation."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_legacy_mapping_safety"
down_revision: str | None = "0012_local_account_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    household_role = postgresql.ENUM(
        "OWNER", "ADMIN", "EDITOR", "VIEWER", name="household_role", create_type=False
    )
    op.add_column(
        "legacy_identity_mappings",
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "legacy_identity_mappings",
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "legacy_identity_mappings",
        sa.Column(
            "revoked_by_application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
        ),
    )
    op.create_index(
        "ix_legacy_identity_mappings_revoked_by_application_user_id",
        "legacy_identity_mappings",
        ["revoked_by_application_user_id"],
    )
    op.drop_index(
        "ix_legacy_identity_mappings_legacy_identity_id",
        table_name="legacy_identity_mappings",
    )
    op.create_index(
        "ix_legacy_identity_mappings_legacy_identity_id",
        "legacy_identity_mappings",
        ["legacy_identity_id"],
    )
    op.create_index(
        "uq_legacy_identity_mappings_active_identity",
        "legacy_identity_mappings",
        ["legacy_identity_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "legacy_membership_baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_role", household_role),
        sa.UniqueConstraint("application_user_id", "household_id"),
    )
    op.create_index(
        "ix_legacy_membership_baselines_application_user_id",
        "legacy_membership_baselines",
        ["application_user_id"],
    )
    op.create_index(
        "ix_legacy_membership_baselines_household_id",
        "legacy_membership_baselines",
        ["household_id"],
    )
    op.create_table(
        "legacy_membership_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "legacy_identity_mapping_id",
            sa.Uuid(),
            sa.ForeignKey("legacy_identity_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", household_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("legacy_identity_mapping_id", "household_id"),
    )
    op.create_index(
        "ix_legacy_membership_grants_legacy_identity_mapping_id",
        "legacy_membership_grants",
        ["legacy_identity_mapping_id"],
    )
    op.create_index(
        "ix_legacy_membership_grants_household_id",
        "legacy_membership_grants",
        ["household_id"],
    )


def downgrade() -> None:
    op.drop_table("legacy_membership_grants")
    op.drop_table("legacy_membership_baselines")
    op.drop_index(
        "uq_legacy_identity_mappings_active_identity",
        table_name="legacy_identity_mappings",
    )
    op.drop_index(
        "ix_legacy_identity_mappings_legacy_identity_id",
        table_name="legacy_identity_mappings",
    )
    op.execute(sa.text("DELETE FROM legacy_identity_mappings WHERE revoked_at IS NOT NULL"))
    op.create_index(
        "ix_legacy_identity_mappings_legacy_identity_id",
        "legacy_identity_mappings",
        ["legacy_identity_id"],
        unique=True,
    )
    op.drop_index(
        "ix_legacy_identity_mappings_revoked_by_application_user_id",
        table_name="legacy_identity_mappings",
    )
    op.drop_column("legacy_identity_mappings", "revoked_by_application_user_id")
    op.drop_column("legacy_identity_mappings", "revoked_at")
    op.drop_column("legacy_identity_mappings", "last_reconciled_at")
