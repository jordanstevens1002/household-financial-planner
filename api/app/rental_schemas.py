import uuid
from datetime import date
from decimal import Decimal

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


class RentalProfileCreate(DatedRecord):
    display_name: str = Field(min_length=1, max_length=200)
    market_rent_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    charged_rent_amount: Decimal = Field(ge=0, decimal_places=2)
    frequency: PaymentFrequency
    vacancy_rate: Decimal = Field(ge=0, le=100, decimal_places=4)
    management_fee_rate: Decimal = Field(ge=0, le=100, decimal_places=4)
    letting_fee: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    rental_share_percentage: Decimal = Field(gt=0, le=100, decimal_places=4)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def recurring_frequency_required(self) -> RentalProfileCreate:
        if self.frequency == PaymentFrequency.ONCE:
            raise ValueError("rental income requires a recurring frequency")
        return self


class RentalProfileRead(RentalProfileCreate, ORMModel):
    id: uuid.UUID
    property_id: uuid.UUID


class PropertyExpenseCreate(DatedRecord):
    expense_type_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(ge=0, decimal_places=2)
    frequency: PaymentFrequency
    is_rental_expense: bool
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def one_off_has_one_date(self) -> PropertyExpenseCreate:
        if self.frequency == PaymentFrequency.ONCE and self.effective_to not in (
            None,
            self.effective_from,
        ):
            raise ValueError("one-off expenses cannot span a date range")
        return self


class PropertyExpenseRead(PropertyExpenseCreate, ORMModel):
    id: uuid.UUID
    property_id: uuid.UUID


class PropertyCashflowRead(BaseModel):
    property_id: uuid.UUID
    from_date: date
    to_date: date
    currency: str
    gross_rent: Decimal
    vacancy_cost: Decimal
    management_fee: Decimal
    letting_fees: Decimal
    property_expenses: Decimal
    net_cashflow: Decimal
    market_rent_equivalent: Decimal
    charged_rent_equivalent: Decimal
    rent_difference: Decimal
    rental_days: int
    warnings: list[str]
