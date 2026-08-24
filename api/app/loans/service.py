"""Shared loan persistence operations."""

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.loans.schemas import LoanCreate
from app.models import Household, Loan, LoanGroup, LookupItem, Property


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
    values = payload.model_dump()
    values["currency"] = payload.currency or household.currency
    loan = Loan(household_id=household_id, **values)
    session.add(loan)
    await session.flush()
    return loan
