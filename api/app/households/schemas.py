"""Household, membership, people, and lookup API schemas."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import HouseholdRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(ORMModel):
    id: uuid.UUID
    oidc_subject: str
    email: str | None
    display_name: str | None


class HouseholdCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    jurisdiction: str | None = Field(default=None, max_length=50)


class HouseholdRead(ORMModel):
    id: uuid.UUID
    display_name: str
    currency: str
    jurisdiction: str | None


class MembershipRead(ORMModel):
    id: uuid.UUID
    household_id: uuid.UUID
    application_user_id: uuid.UUID
    role: HouseholdRole


class PersonCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    tax_residency_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    tax_jurisdiction: str | None = Field(default=None, max_length=50)
    is_active: bool = True
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> PersonCreate:
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class PersonRead(PersonCreate, ORMModel):
    id: uuid.UUID
    household_id: uuid.UUID


class LookupRead(ORMModel):
    id: uuid.UUID
    category: str
    code: str
    display_name: str
    is_active: bool
    generates_rental_income: bool | None
    applies_vacancy: bool | None
    applies_management_fee: bool | None
    applies_rental_expenses: bool | None
    is_occupied_by_household: bool | None
    is_active_asset: bool | None
