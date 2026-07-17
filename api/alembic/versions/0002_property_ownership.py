"""Create Phase 2 property and ownership tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_property_ownership"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    valuation_type = sa.Enum(
        "PURCHASE_PRICE",
        "USER_ESTIMATE",
        "FORMAL_VALUATION",
        "AGENT_APPRAISAL",
        "AUTOMATED_ESTIMATE",
        "SALE_PRICE",
        "SCENARIO_VALUE",
        name="valuation_type",
    )
    owner_type = sa.Enum(
        "PERSON",
        "HOUSEHOLD",
        "COMPANY",
        "TRUST",
        "SUPER_FUND",
        "EXTERNAL_PARTY",
        "OTHER",
        name="owner_type",
    )
    op.create_table(
        "properties",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("property_type_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("current_status_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("address_line_1", sa.String(200)),
        sa.Column("address_line_2", sa.String(200)),
        sa.Column("suburb_or_locality", sa.String(120)),
        sa.Column("state_or_region", sa.String(120)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("purchase_date", sa.Date()),
        sa.Column("sale_date", sa.Date()),
        sa.Column("purchase_price", sa.Numeric(18, 2)),
        sa.Column("default_currency", sa.String(3), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "sale_date IS NULL OR purchase_date IS NULL OR sale_date >= purchase_date"
        ),
    )
    op.create_index("ix_properties_household_id", "properties", ["household_id"])
    op.create_table(
        "property_valuations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Uuid(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 2), nullable=False),
        sa.Column("valuation_type", valuation_type, nullable=False),
        sa.Column("source", sa.String(200)),
        sa.Column("is_estimate", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.UniqueConstraint("property_id", "valuation_date", "valuation_type"),
        sa.CheckConstraint("value > 0"),
    )
    op.create_index("ix_property_valuations_property_id", "property_valuations", ["property_id"])
    op.create_table(
        "property_ownership_interests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Uuid(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_type", owner_type, nullable=False),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="RESTRICT")),
        sa.Column("external_owner_name", sa.String(200)),
        sa.Column("ownership_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("notes", sa.String(2000)),
        sa.CheckConstraint("ownership_percentage > 0 AND ownership_percentage <= 100"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    op.create_index(
        "ix_property_ownership_interests_property_id",
        "property_ownership_interests",
        ["property_id"],
    )
    op.create_table(
        "property_baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "property_id",
            sa.Uuid(),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("baseline_date", sa.Date(), nullable=False),
        sa.Column("property_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("loan_balance_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status_id", sa.Uuid(), sa.ForeignKey("lookup_items.id"), nullable=False),
        sa.Column("accumulated_cost_base", sa.Numeric(18, 2)),
        sa.Column("notes", sa.String(2000)),
        sa.UniqueConstraint("property_id", "baseline_date"),
        sa.CheckConstraint("property_value > 0"),
        sa.CheckConstraint("loan_balance_total >= 0"),
    )
    op.create_index("ix_property_baselines_property_id", "property_baselines", ["property_id"])


def downgrade() -> None:
    op.drop_table("property_baselines")
    op.drop_table("property_ownership_interests")
    op.drop_table("property_valuations")
    op.drop_table("properties")
    sa.Enum(name="owner_type").drop(op.get_bind())
    sa.Enum(name="valuation_type").drop(op.get_bind())
