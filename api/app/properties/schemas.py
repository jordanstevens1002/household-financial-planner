"""Property and ownership API schemas."""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import OwnerType, ValuationType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PropertyCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    property_type_id: uuid.UUID
    current_status_id: uuid.UUID
    address_line_1: str | None = Field(default=None, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    suburb_or_locality: str | None = Field(default=None, max_length=120)
    state_or_region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    purchase_date: date | None = None
    sale_date: date | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    default_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def property_dates_are_ordered(self) -> PropertyCreate:
        if self.sale_date and self.purchase_date and self.sale_date < self.purchase_date:
            raise ValueError("sale_date must not precede purchase_date")
        return self


class PropertyRead(PropertyCreate, ORMModel):
    id: uuid.UUID
    household_id: uuid.UUID
    default_currency: str


class ValuationCreate(BaseModel):
    valuation_date: date
    value: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    valuation_type: ValuationType
    source: str | None = Field(default=None, max_length=200)
    is_estimate: bool
    notes: str | None = Field(default=None, max_length=2000)


class ValuationRead(ValuationCreate, ORMModel):
    id: uuid.UUID
    property_id: uuid.UUID


class OwnershipCreate(BaseModel):
    owner_type: OwnerType
    person_id: uuid.UUID | None = None
    external_owner_name: str | None = Field(default=None, min_length=1, max_length=200)
    ownership_percentage: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def ownership_is_consistent(self) -> OwnershipCreate:
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        if self.owner_type == OwnerType.PERSON and self.person_id is None:
            raise ValueError("person_id is required for a PERSON owner")
        if self.owner_type != OwnerType.PERSON and self.person_id is not None:
            raise ValueError("person_id is only valid for a PERSON owner")
        return self


class OwnershipRead(OwnershipCreate, ORMModel):
    id: uuid.UUID
    property_id: uuid.UUID


class OwnershipResult(BaseModel):
    ownership: OwnershipRead
    total_percentage: Decimal
    warnings: list[str]


class BaselineCreate(BaseModel):
    baseline_date: date
    property_value: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    loan_balance_total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    status_id: uuid.UUID
    accumulated_cost_base: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    notes: str | None = Field(default=None, max_length=2000)


class BaselineRead(BaselineCreate, ORMModel):
    id: uuid.UUID
    property_id: uuid.UUID


class PropertySetupMode(StrEnum):
    HISTORICAL_PURCHASE = "HISTORICAL_PURCHASE"
    CURRENT_SNAPSHOT = "CURRENT_SNAPSHOT"


class PropertyWizardCreate(BaseModel):
    mode: PropertySetupMode
    property: PropertyCreate
    valuation: ValuationCreate | None = None
    baseline: BaselineCreate | None = None
    ownership: list[OwnershipCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def mode_requirements_are_present(self) -> PropertyWizardCreate:
        if self.mode == PropertySetupMode.HISTORICAL_PURCHASE:
            if self.property.purchase_date is None or self.property.purchase_price is None:
                raise ValueError("historical purchase requires purchase_date and purchase_price")
        if self.baseline is None:
            raise ValueError("property setup requires a current-position baseline")
        return self


class PropertyWizardRead(BaseModel):
    property: PropertyRead
    valuation: ValuationRead | None
    baseline: BaselineRead | None
    ownership: list[OwnershipRead]
    warnings: list[str]
