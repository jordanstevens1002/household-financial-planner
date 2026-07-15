"""Create Phase 1 foundation tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role = sa.Enum("OWNER", "ADMIN", "EDITOR", "VIEWER", name="household_role")
    op.create_table(
        "application_users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("oidc_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("display_name", sa.String(200)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_application_users_oidc_subject",
        "application_users",
        ["oidc_subject"],
        unique=True,
    )
    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("jurisdiction", sa.String(50)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "household_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", role, nullable=False),
        sa.UniqueConstraint("household_id", "application_user_id"),
    )
    op.create_index(
        "ix_household_memberships_household_id", "household_memberships", ["household_id"]
    )
    op.create_index(
        "ix_household_memberships_application_user_id",
        "household_memberships",
        ["application_user_id"],
    )
    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey("households.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("legal_name", sa.String(200)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("tax_residency_country", sa.String(2)),
        sa.Column("tax_jurisdiction", sa.String(50)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("notes", sa.String(2000)),
    )
    op.create_index("ix_people_household_id", "people", ["household_id"])
    op.create_table(
        "lookup_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("generates_rental_income", sa.Boolean()),
        sa.Column("applies_vacancy", sa.Boolean()),
        sa.Column("applies_management_fee", sa.Boolean()),
        sa.Column("applies_landlord_expenses", sa.Boolean()),
        sa.Column("is_occupied_by_household", sa.Boolean()),
        sa.Column("is_active_asset", sa.Boolean()),
        sa.UniqueConstraint("category", "code"),
    )
    op.create_index("ix_lookup_items_category", "lookup_items", ["category"])
    lookup = sa.table(
        "lookup_items",
        sa.column("id", sa.Uuid()),
        sa.column("category"),
        sa.column("code"),
        sa.column("display_name"),
        sa.column("is_active"),
        sa.column("generates_rental_income", sa.Boolean()),
        sa.column("applies_vacancy", sa.Boolean()),
        sa.column("applies_management_fee", sa.Boolean()),
        sa.column("applies_landlord_expenses", sa.Boolean()),
        sa.column("is_occupied_by_household", sa.Boolean()),
        sa.column("is_active_asset", sa.Boolean()),
    )
    import uuid

    rows = []
    categories = {
        "property_type": [
            "APARTMENT",
            "UNIT",
            "TOWNHOUSE",
            "SEMI_DETACHED",
            "TERRACE",
            "FREESTANDING_HOUSE",
            "DUPLEX",
            "VILLA",
            "RURAL_RESIDENTIAL",
            "FARM",
            "VACANT_LAND",
            "COMMERCIAL",
            "INDUSTRIAL",
            "RETAIL",
            "MIXED_USE",
            "HOLIDAY_PROPERTY",
            "OTHER",
        ],
        "loan_type": [
            "PRINCIPAL_AND_INTEREST",
            "INTEREST_ONLY",
            "FIXED_RATE",
            "VARIABLE_RATE",
            "CONSTRUCTION",
            "LINE_OF_CREDIT",
            "PERSONAL",
            "OTHER",
        ],
        "income_type": [
            "SALARY",
            "WAGES",
            "BONUS",
            "OVERTIME",
            "CONTRACTING",
            "BUSINESS",
            "RENTAL_DISTRIBUTION",
            "PENSION",
            "GOVERNMENT_PAYMENT",
            "INVESTMENT_INCOME",
            "OTHER_TAXABLE",
            "OTHER_NON_TAXABLE",
        ],
        "retirement_account_type": [
            "AUSTRALIAN_SUP",
            "DEFINED_BENEFIT",
            "PENSION_ACCOUNT",
            "RETIREMENT_SAVINGS",
            "EMPLOYER_PLAN",
            "SELF_MANAGED_SUP_FUND",
            "OTHER",
        ],
    }
    for category, codes in categories.items():
        rows.extend(
            {
                "id": uuid.uuid4(),
                "category": category,
                "code": code,
                "display_name": code.replace("_", " ").title(),
                "is_active": True,
            }
            for code in codes
        )
    statuses = [
        ("PLANNED", False, False, False, False, False, False),
        ("UNDER_CONTRACT", False, False, False, False, False, False),
        ("OWNER_OCCUPIED", False, False, False, False, True, True),
        ("RENTED", True, True, True, True, False, True),
        ("FAMILY_OCCUPIED", False, False, False, False, False, True),
        ("PARTIALLY_RENTED", True, True, True, True, True, True),
        ("SHORT_TERM_RENTAL", True, True, True, True, False, True),
        ("VACANT", False, False, False, True, False, True),
        ("RENOVATING", False, False, False, True, False, True),
        ("CONSTRUCTION", False, False, False, True, False, True),
        ("SOLD", False, False, False, False, False, False),
        ("TRANSFERRED", False, False, False, False, False, False),
        ("ARCHIVED", False, False, False, False, False, False),
    ]
    rows.extend(
        {
            "id": uuid.uuid4(),
            "category": "property_status",
            "code": code,
            "display_name": code.replace("_", " ").title(),
            "is_active": True,
            "generates_rental_income": rent,
            "applies_vacancy": vacancy,
            "applies_management_fee": management,
            "applies_landlord_expenses": expenses,
            "is_occupied_by_household": occupied,
            "is_active_asset": active,
        }
        for code, rent, vacancy, management, expenses, occupied, active in statuses
    )
    op.bulk_insert(lookup, rows)


def downgrade() -> None:
    op.drop_table("lookup_items")
    op.drop_table("people")
    op.drop_table("household_memberships")
    op.drop_table("households")
    op.drop_table("application_users")
    sa.Enum(name="household_role").drop(op.get_bind())
