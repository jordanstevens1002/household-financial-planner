"""Require one tax profile per person and effective date."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_unique_tax_profile_dates"
down_revision: str | None = "0014_legacy_migration_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "person_tax_profiles",
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, row_number() OVER (
                    PARTITION BY person_id, effective_from ORDER BY id DESC
                ) AS position
                FROM person_tax_profiles
            )
            UPDATE person_tax_profiles
            SET superseded_at = CURRENT_TIMESTAMP
            FROM ranked
            WHERE person_tax_profiles.id = ranked.id AND ranked.position > 1
            """
        )
    )
    op.create_index(
        "uq_person_tax_profiles_active_date",
        "person_tax_profiles",
        ["person_id", "effective_from"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
        sqlite_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_person_tax_profiles_active_date",
        "person_tax_profiles",
    )
    op.drop_column("person_tax_profiles", "superseded_at")
