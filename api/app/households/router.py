"""Household, membership, people, and lookup API routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import current_user, require_household_role
from app.households.schemas import (
    HouseholdCreate,
    HouseholdRead,
    LookupRead,
    MembershipRead,
    PersonCreate,
    PersonRead,
    UserRead,
)
from app.models import (
    ApplicationUser,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    Person,
)

router = APIRouter(prefix="/api/v1", tags=["households"])


@router.get("/me", response_model=UserRead)
async def me(user: ApplicationUser = Depends(current_user)) -> ApplicationUser:
    return user


@router.get("/households", response_model=list[HouseholdRead])
async def list_households(
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Household]:
    result = await session.scalars(
        select(Household)
        .join(HouseholdMembership)
        .where(HouseholdMembership.application_user_id == user.id)
    )
    return list(result)


@router.post("/households", response_model=HouseholdRead, status_code=201)
async def create_household(
    payload: HouseholdCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Household:
    household = Household(**payload.model_dump())
    session.add(household)
    await session.flush()
    session.add(
        HouseholdMembership(
            household_id=household.id,
            application_user_id=user.id,
            role=HouseholdRole.OWNER,
        )
    )
    await session.commit()
    await session.refresh(household)
    return household


@router.get("/households/{household_id}", response_model=HouseholdRead)
async def get_household(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> Household:
    household = await session.get(Household, household_id)
    if household is None:
        raise HTTPException(404, "Household not found")
    return household


@router.get("/households/{household_id}/memberships", response_model=list[MembershipRead])
async def list_memberships(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.ADMIN))],
    session: AsyncSession = Depends(get_session),
) -> list[HouseholdMembership]:
    return list(
        await session.scalars(
            select(HouseholdMembership).where(HouseholdMembership.household_id == household_id)
        )
    )


@router.get("/households/{household_id}/people", response_model=list[PersonRead])
async def list_people(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Person]:
    return list(await session.scalars(select(Person).where(Person.household_id == household_id)))


@router.post("/households/{household_id}/people", response_model=PersonRead, status_code=201)
async def create_person(
    household_id: uuid.UUID,
    payload: PersonCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Person:
    person = Person(household_id=household_id, **payload.model_dump())
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return person


@router.get("/lookups/{category}", response_model=list[LookupRead])
async def list_lookups(
    category: str,
    active_only: bool = Query(default=True),
    _: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LookupItem]:
    query = select(LookupItem).where(LookupItem.category == category)
    if active_only:
        query = query.where(LookupItem.is_active.is_(True))
    return list(await session.scalars(query.order_by(LookupItem.display_name)))
