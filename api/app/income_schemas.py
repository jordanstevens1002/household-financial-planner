import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    resident: bool = True
    deductions: Decimal = Field(default=Decimal("0"), ge=0)
    reportable_super_contributions: Decimal = Field(default=Decimal("0"), ge=0)
    include_medicare_levy: bool = True
    medicare_levy_surcharge_rate: Decimal = Field(default=Decimal("0"), ge=0, le=2)
    has_study_loan: bool = False
    manual_annual_net_income: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def manual_net_is_present(self) -> TaxSettings:
        if self.calculation_mode == "MANUAL_NET" and self.manual_annual_net_income is None:
            raise ValueError("manual_annual_net_income is required for MANUAL_NET")
        return self


class TaxProfileCreate(DatedRecord):
    jurisdiction: str = Field(min_length=2, max_length=50)
    tax_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    settings: TaxSettings


class TaxProfileRead(TaxProfileCreate, ORMModel):
    id: uuid.UUID
    person_id: uuid.UUID


class TaxCalculationRequest(BaseModel):
    jurisdiction: str
    tax_year: str
    gross_taxable_income: Decimal = Field(ge=0)
    settings: TaxSettings = Field(default_factory=TaxSettings)


class TaxCalculationRead(BaseModel):
    jurisdiction: str
    tax_year: str
    taxable_income: Decimal
    income_tax: Decimal
    offsets: Decimal
    medicare_levy: Decimal
    medicare_levy_surcharge: Decimal
    study_loan_repayment: Decimal
    total: Decimal
    net_income: Decimal
    warnings: list[str]


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


class HouseholdCashflowRead(BaseModel):
    household_id: uuid.UUID
    as_of: date
    currency: str
    people: list[PersonIncomeProjection]
    annual_gross_income: Decimal
    annual_net_income: Decimal
    annual_expenses: Decimal
    annual_surplus: Decimal
    monthly_net_income: Decimal
    monthly_expenses: Decimal
    monthly_surplus: Decimal
    warnings: list[str]
