"""Create Phase 8 purchase planning structures."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_purchase_planner"
down_revision: str | None = "0007_retirement_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PURCHASE_TYPES = ["HOME", "INVESTMENT_PROPERTY", "LAND", "BUSINESS", "VEHICLE", "OTHER"]


def upgrade() -> None:
    op.create_table(
        "purchase_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("purchase_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("target_location", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("intended_use", sa.String(100), nullable=False),
        sa.Column("target_price_min", sa.Numeric(18, 2), nullable=False),
        sa.Column("target_price_max", sa.Numeric(18, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("desired_buffer", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_lvr", sa.Numeric(7, 4)),
        sa.Column("minimum_monthly_surplus", sa.Numeric(18, 2)),
        sa.Column("provider_code", sa.String(80)),
        sa.Column("provider_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("target_price_min >= 0"),
        sa.CheckConstraint("target_price_max >= target_price_min"),
        sa.CheckConstraint("desired_buffer >= 0"),
        sa.CheckConstraint("max_lvr IS NULL OR (max_lvr >= 0 AND max_lvr <= 100)"),
    )
    op.create_index("ix_purchase_plans_household_id", "purchase_plans", ["household_id"])
    op.create_table(
        "purchase_funding_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_plan_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("available_date", sa.Date(), nullable=False),
        sa.Column("is_borrowed", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("amount >= 0"),
    )
    op.create_index(
        "ix_purchase_funding_sources_purchase_plan_id",
        "purchase_funding_sources",
        ["purchase_plan_id"],
    )
    op.create_table(
        "purchase_costs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_plan_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("is_estimate", sa.Boolean(), nullable=False),
        sa.CheckConstraint("amount >= 0"),
    )
    op.create_index("ix_purchase_costs_purchase_plan_id", "purchase_costs", ["purchase_plan_id"])
    op.create_table(
        "purchase_ownership_allocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_plan_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_type", postgresql.ENUM(name="owner_type", create_type=False), nullable=False
        ),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="RESTRICT")),
        sa.Column("external_owner_name", sa.String(200)),
        sa.Column("ownership_percentage", sa.Numeric(7, 4), nullable=False),
        sa.CheckConstraint("ownership_percentage > 0 AND ownership_percentage <= 100"),
    )
    op.create_index(
        "ix_purchase_ownership_allocations_purchase_plan_id",
        "purchase_ownership_allocations",
        ["purchase_plan_id"],
    )
    lookup = sa.table(
        "lookup_items",
        sa.column("id", sa.Uuid()),
        sa.column("category", sa.String()),
        sa.column("code", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        lookup,
        [
            {
                "id": uuid.uuid4(),
                "category": "purchase_type",
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "is_active": True,
            }
            for code in PURCHASE_TYPES
        ],
    )


def downgrade() -> None:
    op.drop_table("purchase_ownership_allocations")
    op.drop_table("purchase_costs")
    op.drop_table("purchase_funding_sources")
    op.drop_table("purchase_plans")
