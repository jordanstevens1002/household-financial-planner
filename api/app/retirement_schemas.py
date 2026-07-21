import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import RetirementEventType


class RetirementAccountCreate(BaseModel):
    person_id: uuid.UUID | None = None
    display_name: str = Field(min_length=1, max_length=200)
    account_type_id: uuid.UUID
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    opening_balance: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    opening_balance_date: date
    expected_return_rate: Decimal = Field(ge=-100, le=100, decimal_places=4)
    annual_fees: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    retirement_age: int | None = Field(default=None, ge=0, le=120)
    provider_code: str | None = Field(default=None, min_length=1, max_length=80)
    provider_settings: dict[str, object] = Field(default_factory=dict)
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def settings_require_provider(self) -> RetirementAccountCreate:
        if self.provider_settings and self.provider_code is None:
            raise ValueError("provider_settings require provider_code")
        if self.provider_code is not None:
            self.provider_code = self.provider_code.strip().upper()
        return self


class RetirementAccountUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    expected_return_rate: Decimal = Field(ge=-100, le=100, decimal_places=4)
    annual_fees: Decimal = Field(ge=0, decimal_places=2)
    retirement_age: int | None = Field(default=None, ge=0, le=120)
    provider_code: str | None = Field(default=None, min_length=1, max_length=80)
    provider_settings: dict[str, object] = Field(default_factory=dict)
    is_active: bool
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def settings_require_provider(self) -> RetirementAccountUpdate:
        if self.provider_settings and self.provider_code is None:
            raise ValueError("provider_settings require provider_code")
        if self.provider_code is not None:
            self.provider_code = self.provider_code.strip().upper()
        return self


class RetirementAccountRead(RetirementAccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID
    currency: str


class ContributionProfileCreate(BaseModel):
    effective_from: date
    effective_to: date | None = None
    employer_rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=4)
    employer_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    voluntary_pre_tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    voluntary_post_tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    contribution_tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    annual_pre_tax_cap: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_profile(self) -> ContributionProfileCreate:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        if self.employer_rate is not None and self.employer_amount is not None:
            raise ValueError("use employer_rate or employer_amount, not both")
        return self


class ContributionProfileRead(ContributionProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    retirement_account_id: uuid.UUID


class RetirementEventCreate(BaseModel):
    event_type: RetirementEventType = RetirementEventType.BALANCE_ADJUSTMENT
    effective_date: date
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class RetirementEventRead(RetirementEventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    retirement_account_id: uuid.UUID


class RetirementProjectionEntry(BaseModel):
    projection_date: date
    opening_balance: Decimal
    employer_contributions: Decimal
    voluntary_pre_tax_contributions: Decimal
    voluntary_post_tax_contributions: Decimal
    contribution_tax: Decimal
    fees: Decimal
    earnings: Decimal
    balance_adjustments: Decimal
    closing_balance: Decimal


class RetirementProjectionRead(BaseModel):
    account_id: uuid.UUID
    calculation_date: date
    projection_date: date
    currency: str
    provider_code: str | None
    entries: list[RetirementProjectionEntry]
    projected_balance: Decimal
    total_contributions: Decimal
    total_contribution_tax: Decimal
    total_fees: Decimal
    total_earnings: Decimal
    assumptions_used: list[str]
    warnings: list[str]
