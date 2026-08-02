"""Income, tax, and household cash-flow API schemas."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import PaymentFrequency


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DatedRecord(BaseModel):
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def dates_are_ordered(self) -> DatedRecord:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class IncomeSourceCreate(DatedRecord):
    income_type_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=200)
    gross_amount: Decimal = Field(ge=0, decimal_places=2)
    frequency: PaymentFrequency
    salary_sacrifice_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    annual_growth_rate: Decimal | None = Field(default=None, ge=-100, le=100, decimal_places=4)
    taxable: bool
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def income_is_recurring(self) -> IncomeSourceCreate:
        if self.frequency == PaymentFrequency.ONCE:
            raise ValueError("income sources require a recurring frequency")
        return self


class IncomeSourceRead(IncomeSourceCreate, ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID


class TaxSettings(BaseModel):
    calculation_mode: Literal["AUTOMATIC", "MANUAL_NET"] = "AUTOMATIC"
    parameters: dict[str, object] = Field(default_factory=dict)
    manual_annual_net_income: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def manual_net_is_present(self) -> TaxSettings:
        if self.calculation_mode == "MANUAL_NET" and self.manual_annual_net_income is None:
            raise ValueError("manual_annual_net_income is required for MANUAL_NET")
        return self


class TaxProfileCreate(DatedRecord):
    jurisdiction: str = Field(min_length=2, max_length=50)
    tax_year: str = Field(min_length=1, max_length=20)
    settings: TaxSettings

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, value: str) -> str:
        return value.strip().upper()


class TaxProfileRead(TaxProfileCreate, ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID


class TaxProviderRead(BaseModel):
    jurisdiction: str
    display_name: str
    supported_tax_years: list[str]


class TaxCalculationRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    jurisdiction: str = Field(min_length=2, max_length=50)
    tax_year: str = Field(min_length=1, max_length=20)
    gross_taxable_income: Decimal = Field(ge=0)
    settings: TaxSettings = Field(default_factory=TaxSettings)

    @field_validator("currency", "jurisdiction")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def manual_net_does_not_exceed_gross(self) -> TaxCalculationRequest:
        if (
            self.settings.calculation_mode == "MANUAL_NET"
            and self.settings.manual_annual_net_income is not None
            and self.settings.manual_annual_net_income > self.gross_taxable_income
        ):
            raise ValueError("manual_annual_net_income must not exceed gross_taxable_income")
        return self


class TaxComponentRead(BaseModel):
    code: str
    display_name: str
    amount: Decimal


class TaxCalculationRead(BaseModel):
    jurisdiction: str
    tax_year: str
    ruleset_version: str
    taxable_income: Decimal
    components: list[TaxComponentRead]
    total: Decimal
    net_income: Decimal
    warnings: list[str]


class StandaloneTaxCalculationRead(TaxCalculationRead):
    currency: str


class HouseholdExpenseCreate(DatedRecord):
    person_id: uuid.UUID | None = None
    category_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0, decimal_places=2)
    frequency: PaymentFrequency
    annual_growth_rate: Decimal | None = Field(default=None, ge=-100, le=100, decimal_places=4)
    is_essential: bool
    notes: str | None = Field(default=None, max_length=2000)


class HouseholdExpenseRead(HouseholdExpenseCreate, ORMModel):
    id: uuid.UUID
    household_id: uuid.UUID


class PersonIncomeProjection(BaseModel):
    person_id: uuid.UUID
    display_name: str
    gross_taxable_income: Decimal
    non_taxable_income: Decimal
    net_income: Decimal
    tax_and_repayments: Decimal
    calculation_mode: Literal["AUTOMATIC", "MANUAL_NET", "NO_PROFILE"]
    warnings: list[str]


class LoanRepaymentAllocationRead(BaseModel):
    person_id: uuid.UUID
    display_name: str
    responsibility_percentage: Decimal
    annual_amount: Decimal
    monthly_amount: Decimal


class LoanRepaymentProjectionRead(BaseModel):
    loan_id: uuid.UUID
    property_id: uuid.UUID | None
    display_name: str
    currency: str
    repayment_frequency: str
    periodic_repayment: Decimal
    annual_repayment: Decimal
    monthly_repayment: Decimal
    included_in_household_total: bool
    allocations: list[LoanRepaymentAllocationRead]
    warnings: list[str]


class HouseholdCashflowRead(BaseModel):
    household_id: uuid.UUID
    as_of: date
    currency: str
    people: list[PersonIncomeProjection]
    annual_gross_income: Decimal
    annual_net_income: Decimal
    annual_ordinary_expenses: Decimal
    annual_loan_repayments: Decimal
    annual_expenses: Decimal
    annual_surplus: Decimal
    monthly_net_income: Decimal
    monthly_ordinary_expenses: Decimal
    monthly_loan_repayments: Decimal
    monthly_expenses: Decimal
    monthly_surplus: Decimal
    loan_repayments: list[LoanRepaymentProjectionRead]
    warnings: list[str]
