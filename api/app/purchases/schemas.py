"""Purchase-planning API schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import OwnerType

Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class PurchaseProviderRead(BaseModel):
    code: str
    display_name: str


class FundingSourceCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=80)
    amount: NonNegativeMoney
    available_date: date
    is_borrowed: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class FundingSourceRead(FundingSourceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    purchase_plan_id: uuid.UUID
    revision: int


class FundingSourceUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: str | None = Field(default=None, min_length=1, max_length=80)
    amount: NonNegativeMoney | None = None
    available_date: date | None = None
    is_borrowed: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_correction(self) -> FundingSourceUpdate:
        mutable_fields = self.model_fields_set - {"expected_revision"}
        if not mutable_fields:
            raise ValueError("At least one funding source field must be corrected")
        required_fields = {
            "display_name",
            "source_type",
            "amount",
            "available_date",
            "is_borrowed",
        }
        if any(getattr(self, field) is None for field in mutable_fields & required_fields):
            raise ValueError("Required funding source fields cannot be null")
        return self


class CostCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    amount: NonNegativeMoney
    is_estimate: bool = True


class CostRead(CostCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    purchase_plan_id: uuid.UUID
    revision: int


class CostUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    code: str | None = Field(default=None, min_length=1, max_length=80)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: NonNegativeMoney | None = None
    is_estimate: bool | None = None

    @model_validator(mode="after")
    def validate_correction(self) -> CostUpdate:
        mutable_fields = self.model_fields_set - {"expected_revision"}
        if not mutable_fields:
            raise ValueError("At least one purchase cost field must be corrected")
        if any(getattr(self, field) is None for field in mutable_fields):
            raise ValueError("Purchase cost fields cannot be null")
        return self


class OwnershipCreate(BaseModel):
    owner_type: OwnerType
    person_id: uuid.UUID | None = None
    external_owner_name: str | None = Field(default=None, max_length=200)
    ownership_percentage: Decimal = Field(gt=0, le=100)

    @model_validator(mode="after")
    def validate_owner(self) -> OwnershipCreate:
        if self.owner_type == OwnerType.PERSON:
            if self.person_id is None:
                raise ValueError("PERSON ownership requires person_id")
            if self.external_owner_name is not None:
                raise ValueError("PERSON ownership cannot have an external owner name")
        elif self.person_id is not None:
            raise ValueError("Only PERSON ownership can reference person_id")
        if self.owner_type == OwnerType.EXTERNAL_PARTY:
            if not self.external_owner_name or not self.external_owner_name.strip():
                raise ValueError("EXTERNAL_PARTY ownership requires external_owner_name")
            self.external_owner_name = self.external_owner_name.strip()
        elif self.external_owner_name is not None:
            raise ValueError("External owner name requires EXTERNAL_PARTY ownership")
        return self


class PurchaseOwnershipRead(OwnershipCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    purchase_plan_id: uuid.UUID
    revision: int


class OwnershipSetReplace(BaseModel):
    expected_revision_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    ownership: list[OwnershipCreate] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_set(self) -> OwnershipSetReplace:
        if len(set(self.expected_revision_ids)) != len(self.expected_revision_ids):
            raise ValueError("expected_revision_ids must be unique")
        if sum(item.ownership_percentage for item in self.ownership) != 100:
            raise ValueError("ownership percentages must total 100")
        return self


class ChildRetire(BaseModel):
    expected_revision: int = Field(ge=1)


class PurchasePlanCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    purchase_type_id: uuid.UUID
    target_location: dict[str, object] = Field(default_factory=dict)
    intended_use: str = Field(min_length=1, max_length=100)
    target_price_min: NonNegativeMoney
    target_price_max: NonNegativeMoney
    target_date: date
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    desired_buffer: NonNegativeMoney = Decimal("0")
    max_lvr: Decimal | None = Field(default=None, ge=0, le=100)
    minimum_monthly_surplus: Money | None = None
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


class PurchasePlanDetail(PurchasePlanRead):
    funding_sources: list[FundingSourceRead]
    costs: list[CostRead]
    ownership: list[PurchaseOwnershipRead]


class FeasibilityRequest(BaseModel):
    purchase_price: Money = Field(gt=0)
    desired_buffer: NonNegativeMoney | None = None
    provider_settings: dict[str, object] | None = None
    maximum_additional_borrowing: NonNegativeMoney
    annual_interest_rate: Decimal = Field(ge=0, le=100)
    loan_term_years: int = Field(gt=0, le=100)
    current_monthly_surplus: Money


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
