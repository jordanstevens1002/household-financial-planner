import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HouseholdRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class ValuationType(StrEnum):
    PURCHASE_PRICE = "PURCHASE_PRICE"
    USER_ESTIMATE = "USER_ESTIMATE"
    FORMAL_VALUATION = "FORMAL_VALUATION"
    AGENT_APPRAISAL = "AGENT_APPRAISAL"
    AUTOMATED_ESTIMATE = "AUTOMATED_ESTIMATE"
    SALE_PRICE = "SALE_PRICE"
    SCENARIO_VALUE = "SCENARIO_VALUE"


class OwnerType(StrEnum):
    PERSON = "PERSON"
    HOUSEHOLD = "HOUSEHOLD"
    COMPANY = "COMPANY"
    TRUST = "TRUST"
    SUPER_FUND = "SUPER_FUND"
    EXTERNAL_PARTY = "EXTERNAL_PARTY"
    OTHER = "OTHER"


class EventClassification(StrEnum):
    OBSERVED = "OBSERVED"
    PLANNED = "PLANNED"
    PROJECTED = "PROJECTED"


class ApplicationUser(Base):
    __tablename__ = "application_users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    oidc_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Household(Base):
    __tablename__ = "households"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    jurisdiction: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    memberships: Mapped[list[HouseholdMembership]] = relationship(cascade="all, delete-orphan")


class HouseholdMembership(Base):
    __tablename__ = "household_memberships"
    __table_args__ = (UniqueConstraint("household_id", "application_user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    application_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[HouseholdRole] = mapped_column(Enum(HouseholdRole, name="household_role"))


class Person(Base):
    __tablename__ = "people"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    tax_residency_country: Mapped[str | None] = mapped_column(String(2))
    tax_jurisdiction: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(2000))


class LookupItem(Base):
    __tablename__ = "lookup_items"
    __table_args__ = (UniqueConstraint("category", "code"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), index=True)
    code: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    generates_rental_income: Mapped[bool | None] = mapped_column(Boolean)
    applies_vacancy: Mapped[bool | None] = mapped_column(Boolean)
    applies_management_fee: Mapped[bool | None] = mapped_column(Boolean)
    applies_landlord_expenses: Mapped[bool | None] = mapped_column(Boolean)
    is_occupied_by_household: Mapped[bool | None] = mapped_column(Boolean)
    is_active_asset: Mapped[bool | None] = mapped_column(Boolean)


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        CheckConstraint("sale_date IS NULL OR purchase_date IS NULL OR sale_date >= purchase_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(200))
    property_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lookup_items.id"))
    current_status_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lookup_items.id"))
    address_line_1: Mapped[str | None] = mapped_column(String(200))
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    suburb_or_locality: Mapped[str | None] = mapped_column(String(120))
    state_or_region: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country_code: Mapped[str | None] = mapped_column(String(2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    sale_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    default_currency: Mapped[str] = mapped_column(String(3))
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PropertyValuation(Base):
    __tablename__ = "property_valuations"
    __table_args__ = (
        UniqueConstraint("property_id", "valuation_date", "valuation_type"),
        CheckConstraint("value > 0"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    valuation_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    valuation_type: Mapped[ValuationType] = mapped_column(
        Enum(ValuationType, name="valuation_type")
    )
    source: Mapped[str | None] = mapped_column(String(200))
    is_estimate: Mapped[bool] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(String(2000))


class PropertyOwnershipInterest(Base):
    __tablename__ = "property_ownership_interests"
    __table_args__ = (
        CheckConstraint("ownership_percentage > 0 AND ownership_percentage <= 100"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    owner_type: Mapped[OwnerType] = mapped_column(Enum(OwnerType, name="owner_type"))
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="RESTRICT")
    )
    external_owner_name: Mapped[str | None] = mapped_column(String(200))
    ownership_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(2000))


class PropertyBaseline(Base):
    __tablename__ = "property_baselines"
    __table_args__ = (
        UniqueConstraint("property_id", "baseline_date"),
        CheckConstraint("property_value > 0"),
        CheckConstraint("loan_balance_total >= 0"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    baseline_date: Mapped[date] = mapped_column(Date)
    property_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    loan_balance_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lookup_items.id"))
    accumulated_cost_base: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    notes: Mapped[str | None] = mapped_column(String(2000))


class EventType(Base):
    __tablename__ = "event_types"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    priority: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FinancialEvent(Base):
    __tablename__ = "financial_events"
    __table_args__ = (
        CheckConstraint("percentage IS NULL OR (percentage >= 0 AND percentage <= 100)"),
        UniqueConstraint("household_id", "idempotency_key"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    event_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_types.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    payload: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    notes: Mapped[str | None] = mapped_column(String(2000))
    classification: Mapped[EventClassification] = mapped_column(
        Enum(EventClassification, name="event_classification")
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    data_quality_flags: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("application_users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
