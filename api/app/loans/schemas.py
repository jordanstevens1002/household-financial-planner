"""Loan API schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.events.schemas import FinancialEventRead
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
    borrower_person_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=20,
        description="Unordered borrower set; responses use canonical UUID order.",
    )

    @field_validator("account_reference_masked")
    @classmethod
    def account_reference_is_masked(cls, value: str | None) -> str | None:
        if value is None:
            return None
        compact = value.strip()
        if not compact:
            return None
        mask_count = sum(character in "*•xX" for character in compact)
        visible = "".join(character for character in compact if character.isalnum())
        visible = visible.lstrip("xX")
        if mask_count < 3 or not 2 <= len(visible) <= 4:
            raise ValueError(
                "account reference must hide all but the final 2 to 4 characters, "
                "for example ****1234"
            )
        return compact

    @field_validator("borrower_person_ids")
    @classmethod
    def borrowers_are_unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("borrower person IDs must be unique")
        return value


class LoanUpdate(BaseModel):
    loan_group_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    lender: str | None = Field(default=None, max_length=200)
    account_reference_masked: str | None = Field(default=None, max_length=50)
    loan_type_id: uuid.UUID | None = None
    original_balance: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    opening_balance: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    opening_balance_date: date | None = None
    initial_interest_rate: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=7, decimal_places=4
    )
    scheduled_repayment: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    term_months: int | None = Field(default=None, gt=0, le=1200)
    interest_calculation_method: InterestCalculationMethod | None = None
    repayment_frequency: RepaymentFrequency | None = None
    is_interest_only: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("account_reference_masked")
    @classmethod
    def account_reference_is_masked(cls, value: str | None) -> str | None:
        return LoanCreate.account_reference_is_masked(value)

    @model_validator(mode="after")
    def has_changes(self) -> LoanUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one field must be supplied")
        required_when_supplied = {
            "display_name",
            "initial_interest_rate",
            "interest_calculation_method",
            "is_interest_only",
            "loan_type_id",
            "opening_balance",
            "opening_balance_date",
            "repayment_frequency",
        }
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required_when_supplied
        ):
            raise ValueError("required loan fields cannot be cleared")
        return self


class LoanCloseCreate(BaseModel):
    effective_date: date
    notes: str | None = Field(default=None, max_length=2000)


class LoanGroupCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    property_id: uuid.UUID | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("loan group name cannot be empty")
        return normalized


class LoanGroupUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return LoanGroupCreate.normalize_display_name(value)


class LoanGroupRemovalCreate(BaseModel):
    assigned_loan_ids: list[uuid.UUID] = Field(min_length=1, max_length=10_000)

    @field_validator("assigned_loan_ids")
    @classmethod
    def assigned_loans_are_unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise ValueError("assigned loan IDs must be unique")
        return value


class LoanGroupRead(LoanGroupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID


class LoanRead(LoanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID
    currency: str


class LoanBorrowerReplace(BaseModel):
    borrower_person_ids: list[uuid.UUID] = Field(
        max_length=20,
        description="Unordered borrower set; responses use canonical UUID order.",
    )

    @field_validator("borrower_person_ids")
    @classmethod
    def borrowers_are_unique(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        return LoanCreate.borrowers_are_unique(value)


class DebtReconciliationStatus(StrEnum):
    NO_LINKED_LOANS = "NO_LINKED_LOANS"
    RECORDED_DEBT_MISSING = "RECORDED_DEBT_MISSING"
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    UNPROJECTABLE_LOANS = "UNPROJECTABLE_LOANS"


class LoanDebtBalanceRead(BaseModel):
    loan_id: uuid.UUID
    display_name: str
    currency: str
    effective_balance: Decimal | None
    data_quality_flags: list[str] = Field(default_factory=list)


class PropertyDebtReconciliationRead(BaseModel):
    property_id: uuid.UUID
    as_of: date
    currency: str
    baseline_id: uuid.UUID | None
    recorded_debt_date: date | None
    recorded_property_debt: Decimal | None
    linked_loan_balance: Decimal | None
    difference: Decimal | None
    status: DebtReconciliationStatus
    loans: list[LoanDebtBalanceRead]
    warnings: list[str]


class LoanRepaymentResponsibilityCreate(BaseModel):
    person_id: uuid.UUID
    responsibility_percentage: Decimal = Field(gt=0, le=100, decimal_places=2)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> LoanRepaymentResponsibilityCreate:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class LoanRepaymentResponsibilityRead(LoanRepaymentResponsibilityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    loan_id: uuid.UUID


class LoanRepaymentResponsibilityResult(BaseModel):
    responsibility: LoanRepaymentResponsibilityRead
    total_percentage: Decimal
    warnings: list[str]


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
