import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.event_schemas import FinancialEventRead
from app.models import (
    EventClassification,
    InterestCalculationMethod,
    RepaymentFrequency,
)


class LoanCreate(BaseModel):
    property_id: uuid.UUID | None = None
    loan_group_id: uuid.UUID | None = None
    display_name: str = Field(min_length=1, max_length=200)
    lender: str | None = Field(default=None, max_length=200)
    account_reference_masked: str | None = Field(default=None, max_length=50)
    loan_type_id: uuid.UUID
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    original_balance: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    opening_balance: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    opening_balance_date: date
    initial_interest_rate: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    scheduled_repayment: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    term_months: int | None = Field(default=None, gt=0, le=1200)
    interest_calculation_method: InterestCalculationMethod
    repayment_frequency: RepaymentFrequency
    is_interest_only: bool
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=2000)


class LoanGroupCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    property_id: uuid.UUID | None = None


class LoanGroupRead(LoanGroupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID


class LoanRead(LoanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID
    currency: str


class LoanEventCreate(BaseModel):
    event_type_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    effective_at: datetime
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=4)
    payload: dict[str, object] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)
    classification: EventClassification
    is_enabled: bool = True

    @model_validator(mode="after")
    def observed_events_cannot_be_disabled(self) -> LoanEventCreate:
        if self.classification == EventClassification.OBSERVED and not self.is_enabled:
            raise ValueError("observed events cannot be disabled")
        return self


class ScheduleEntry(BaseModel):
    payment_number: int
    payment_date: date
    opening_balance: Decimal
    interest: Decimal
    repayment: Decimal
    principal: Decimal
    offset_balance: Decimal
    closing_balance: Decimal
    annual_interest_rate: Decimal


class LoanScheduleRead(BaseModel):
    loan_id: uuid.UUID
    entries: list[ScheduleEntry]
    total_interest: Decimal
    total_repayments: Decimal
    payoff_date: date | None
    remaining_balance: Decimal
    data_quality_flags: list[str]
    interest_saved_vs_no_offset: Decimal | None = None


class RefinanceCreate(BaseModel):
    effective_at: datetime
    replacement_loan: LoanCreate
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class RefinanceRead(BaseModel):
    closed_loan_id: uuid.UUID
    replacement_loan: LoanRead
    refinance_event: FinancialEventRead


class GoalCreate(BaseModel):
    person_id: uuid.UUID | None = None
    property_id: uuid.UUID | None = None
    loan_id: uuid.UUID | None = None
    goal_type_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    target_percentage: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=4)
    target_date: date | None = None
    target_boolean: bool | None = None
    priority: int = Field(ge=0)
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def exactly_one_target_is_set(self) -> GoalCreate:
        targets = (
            self.target_amount,
            self.target_percentage,
            self.target_date,
            self.target_boolean,
        )
        if sum(value is not None for value in targets) != 1:
            raise ValueError("exactly one goal target must be supplied")
        return self


class GoalRead(GoalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID


class TargetCalculationRequest(BaseModel):
    goal_id: uuid.UUID
    as_of: date


class TargetCalculationRead(BaseModel):
    loan_id: uuid.UUID
    goal_id: uuid.UUID
    required_repayment: Decimal
    repayment_frequency: RepaymentFrequency
    target_amount: Decimal
    within_target: bool
    estimated_payoff_date: date | None
