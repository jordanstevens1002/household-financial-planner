"""Create Phase 9 scenario and override structures."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_scenarios"
down_revision: str | None = "0008_purchase_planner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("template_code", sa.String(80)),
        sa.Column(
            "base_scenario_id", sa.Uuid(), sa.ForeignKey("scenarios.id", ondelete="SET NULL")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_scenarios_household_id", "scenarios", ["household_id"])
    op.create_index("ix_scenarios_base_scenario_id", "scenarios", ["base_scenario_id"])
    op.create_table(
        "scenario_overrides",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "scenario_id",
            sa.Uuid(),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_entity_type", sa.String(80), nullable=False),
        sa.Column("target_entity_id", sa.Uuid()),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("override_key", sa.String(120), nullable=False),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    op.create_index("ix_scenario_overrides_scenario_id", "scenario_overrides", ["scenario_id"])
    op.create_index(
        "ix_scenario_overrides_target_entity_id", "scenario_overrides", ["target_entity_id"]
    )
    op.create_index(
        "ix_scenario_overrides_effective_from", "scenario_overrides", ["effective_from"]
    )


def downgrade() -> None:
    op.drop_table("scenario_overrides")
    op.drop_table("scenarios")
