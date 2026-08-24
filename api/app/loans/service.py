"""Shared loan persistence operations."""

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.loans.schemas import LoanCreate
from app.models import Household, Loan, LoanBorrower, LoanGroup, LookupItem, Person, Property


async def validate_borrowers(
    household_id: uuid.UUID, person_ids: list[uuid.UUID], session: AsyncSession
) -> list[Person]:
    if not person_ids:
        return []
    people = list(
        await session.scalars(
            select(Person).where(Person.id.in_(person_ids), Person.household_id == household_id)
        )
    )
    if len(people) != len(person_ids):
        raise HTTPException(422, "Every borrower must be a person in the loan household")
    people_by_id = {person.id: person for person in people}
    return [people_by_id[person_id] for person_id in person_ids]


def equal_borrower_allocations(person_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """Split 100.00% deterministically without losing rounding remainders."""
    ordered = sorted(set(person_ids), key=lambda person_id: person_id.int)
    if not ordered:
        return {}
    quotient, remainder = divmod(10_000, len(ordered))
    return {
        person_id: (Decimal(quotient + (1 if index < remainder else 0)) / Decimal("100")).quantize(
            Decimal("0.01")
        )
        for index, person_id in enumerate(ordered)
    }


def canonical_borrower_ids(person_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Return the API's stable, unordered-set representation of borrowers."""
    return sorted(set(person_ids), key=lambda person_id: person_id.int)


async def create_loan_record(
    household_id: uuid.UUID, payload: LoanCreate, session: AsyncSession
) -> Loan:
    household = await session.get(Household, household_id)
    if household is None:
        raise HTTPException(404, "Household not found")
    loan_type = await session.get(LookupItem, payload.loan_type_id)
    if loan_type is None or loan_type.category != "loan_type" or not loan_type.is_active:
        raise HTTPException(422, "Active loan_type lookup required")
    if payload.property_id is not None:
        property_record = await session.get(Property, payload.property_id)
        if property_record is None or property_record.household_id != household_id:
            raise HTTPException(422, "Loan property must belong to the household")
    if payload.loan_group_id is not None:
        group = await session.get(LoanGroup, payload.loan_group_id)
        if (
            group is None
            or group.household_id != household_id
            or group.property_id != payload.property_id
        ):
            raise HTTPException(422, "Loan group must belong to the same property and household")
    borrowers = await validate_borrowers(
        household_id, canonical_borrower_ids(payload.borrower_person_ids), session
    )
    values = payload.model_dump(exclude={"borrower_person_ids"})
    values["currency"] = payload.currency or household.currency
    loan = Loan(household_id=household_id, **values)
    loan.borrower_links = [LoanBorrower(person_id=person.id) for person in borrowers]
    session.add(loan)
    await session.flush()
    return loan
