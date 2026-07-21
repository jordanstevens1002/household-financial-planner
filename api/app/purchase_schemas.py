import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import OwnerType


class FundingSourceCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(ge=0)
    available_date: date
    is_borrowed: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class CostCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0)
    is_estimate: bool = True


class OwnershipCreate(BaseModel):
    owner_type: OwnerType
    person_id: uuid.UUID | None = None
    external_owner_name: str | None = Field(default=None, max_length=200)
    ownership_percentage: Decimal = Field(gt=0, le=100)


class PurchasePlanCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    purchase_type_id: uuid.UUID
    target_location: dict[str, object] = Field(default_factory=dict)
    intended_use: str = Field(min_length=1, max_length=100)
    target_price_min: Decimal = Field(ge=0)
    target_price_max: Decimal = Field(ge=0)
    target_date: date
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    desired_buffer: Decimal = Field(default=Decimal("0"), ge=0)
    max_lvr: Decimal | None = Field(default=None, ge=0, le=100)
    minimum_monthly_surplus: Decimal | None = None
    provider_code: str | None = Field(default=None, min_length=1, max_length=80)
    provider_settings: dict[str, object] = Field(default_factory=dict)
    funding_sources: list[FundingSourceCreate] = Field(default_factory=list)
    costs: list[CostCreate] = Field(default_factory=list)
    ownership: list[OwnershipCreate] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_plan(self) -> PurchasePlanCreate:
        if self.target_price_max < self.target_price_min:
            raise ValueError("target_price_max must be at least target_price_min")
        if self.provider_settings and self.provider_code is None:
            raise ValueError("provider_settings require provider_code")
        if self.provider_code is not None:
            self.provider_code = self.provider_code.strip().upper()
        if self.ownership and sum(item.ownership_percentage for item in self.ownership) != 100:
            raise ValueError("ownership percentages must total 100")
        return self


class PurchasePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID
    display_name: str
    purchase_type_id: uuid.UUID
    target_location: dict[str, object]
    intended_use: str
    target_price_min: Decimal
    target_price_max: Decimal
    target_date: date
    currency: str
    desired_buffer: Decimal
    max_lvr: Decimal | None
    minimum_monthly_surplus: Decimal | None
    provider_code: str | None
    provider_settings: dict[str, object]
    notes: str | None


class FeasibilityRequest(BaseModel):
    purchase_price: Decimal = Field(gt=0)
    maximum_additional_borrowing: Decimal = Field(default=Decimal("0"), ge=0)
    annual_interest_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    loan_term_years: int = Field(default=30, gt=0, le=100)
    current_monthly_surplus: Decimal = Decimal("0")


class CalculatedCost(BaseModel):
    code: str
    display_name: str
    amount: Decimal
    source: str


class FeasibilityRead(BaseModel):
    purchase_plan_id: uuid.UUID
    calculation_date: date
    currency: str
    purchase_price: Decimal
    costs: list[CalculatedCost]
    available_equity_funding: Decimal
    existing_borrowed_funding: Decimal
    additional_loan_required: Decimal
    total_debt_funding: Decimal
    monthly_loan_repayment: Decimal
    projected_monthly_surplus: Decimal
    lvr: Decimal
    funding_gap: Decimal
    required_total: Decimal
    is_feasible: bool
    failed_thresholds: list[str]
    assumptions_used: list[str]
    warnings: list[str]
