"""Household, membership, people, and lookup API routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.sessions import utc_now
from app.core.database import get_session
from app.core.dependencies import current_user, require_household_role
from app.core.logging import get_logger
from app.households.schemas import (
    HouseholdCreate,
    HouseholdRead,
    LookupRead,
    MembershipCreate,
    MembershipRead,
    MembershipUpdate,
    PersonCreate,
    PersonRead,
    UserRead,
)
from app.models import (
    ApplicationUser,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LegacyIdentityMapping,
    LegacyMembershipBaseline,
    LegacyMembershipGrant,
    LookupItem,
    Person,
)

router = APIRouter(prefix="/api/v1", tags=["households"])
logger = get_logger(component="household_membership_administration")


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
) -> list[MembershipRead]:
    rows = await session.execute(
        select(HouseholdMembership, ApplicationUser)
        .join(ApplicationUser, ApplicationUser.id == HouseholdMembership.application_user_id)
        .where(HouseholdMembership.household_id == household_id)
        .order_by(ApplicationUser.display_name, ApplicationUser.username, HouseholdMembership.id)
    )
    return [_membership_read(membership, user) for membership, user in rows]


def _membership_read(membership: HouseholdMembership, user: ApplicationUser) -> MembershipRead:
    return MembershipRead(
        id=membership.id,
        household_id=membership.household_id,
        application_user_id=user.id,
        role=membership.role,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
    )


def _assert_role_can_be_managed(actor_role: HouseholdRole, target_role: HouseholdRole) -> None:
    if actor_role != HouseholdRole.OWNER and target_role == HouseholdRole.OWNER:
        raise HTTPException(403, "Only household owners can manage the owner role")


async def _membership_for_update(
    household_id: uuid.UUID,
    membership_id: uuid.UUID,
    session: AsyncSession,
) -> HouseholdMembership:
    membership = await session.scalar(
        select(HouseholdMembership)
        .where(
            HouseholdMembership.id == membership_id,
            HouseholdMembership.household_id == household_id,
        )
        .with_for_update()
    )
    if membership is None:
        raise HTTPException(404, "Household membership not found")
    return membership


async def _protect_final_owner(
    membership: HouseholdMembership,
    session: AsyncSession,
) -> None:
    if membership.role != HouseholdRole.OWNER:
        return
    # All owner removals for a household contend on one row in PostgreSQL. Locking
    # only the selected membership would allow two owners to remove each other
    # concurrently after both observed an owner count of two.
    await session.scalar(
        select(Household).where(Household.id == membership.household_id).with_for_update()
    )
    now = utc_now()
    owner_count = await session.scalar(
        select(func.count())
        .select_from(HouseholdMembership)
        .join(ApplicationUser, ApplicationUser.id == HouseholdMembership.application_user_id)
        .where(
            HouseholdMembership.household_id == membership.household_id,
            HouseholdMembership.role == HouseholdRole.OWNER,
            ApplicationUser.is_active.is_(True),
            or_(
                ApplicationUser.oidc_subject.is_not(None),
                and_(
                    ApplicationUser.username.is_not(None),
                    ApplicationUser.password_hash.is_not(None),
                    ApplicationUser.must_change_password.is_(False),
                    or_(
                        ApplicationUser.password_expires_at.is_(None),
                        ApplicationUser.password_expires_at > now,
                    ),
                ),
            ),
        )
    )
    if owner_count == 1:
        raise HTTPException(409, "The final household owner cannot be removed or demoted")


async def _direct_membership_baseline(
    membership: HouseholdMembership,
    session: AsyncSession,
) -> LegacyMembershipBaseline | None:
    baseline: LegacyMembershipBaseline | None = await session.scalar(
        select(LegacyMembershipBaseline)
        .where(
            LegacyMembershipBaseline.application_user_id == membership.application_user_id,
            LegacyMembershipBaseline.household_id == membership.household_id,
        )
        .with_for_update()
    )
    return baseline


async def _reject_inherited_membership_mutation(
    membership: HouseholdMembership,
    session: AsyncSession,
) -> None:
    inherited = await session.scalar(
        select(LegacyMembershipGrant.id)
        .join(
            LegacyIdentityMapping,
            LegacyIdentityMapping.id == LegacyMembershipGrant.legacy_identity_mapping_id,
        )
        .where(
            LegacyIdentityMapping.application_user_id == membership.application_user_id,
            LegacyIdentityMapping.revoked_at.is_(None),
            LegacyMembershipGrant.household_id == membership.household_id,
            LegacyMembershipGrant.is_active.is_(True),
        )
        .limit(1)
    )
    if inherited is not None:
        raise HTTPException(
            409,
            "Membership is inherited from a legacy identity; change the source membership first",
        )


@router.post(
    "/households/{household_id}/memberships",
    response_model=MembershipRead,
    status_code=201,
)
async def create_membership(
    household_id: uuid.UUID,
    payload: MembershipCreate,
    actor: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.ADMIN))],
    session: AsyncSession = Depends(get_session),
) -> MembershipRead:
    _assert_role_can_be_managed(actor.role, payload.role)
    user = await session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username == payload.username,
            ApplicationUser.is_active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(404, "Active local account not found")
    existing = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(409, "Account is already a household member")
    membership = HouseholdMembership(
        household_id=household_id,
        application_user_id=user.id,
        role=payload.role,
    )
    session.add(membership)
    baseline = await session.scalar(
        select(LegacyMembershipBaseline)
        .where(
            LegacyMembershipBaseline.application_user_id == user.id,
            LegacyMembershipBaseline.household_id == household_id,
        )
        .with_for_update()
    )
    if baseline is not None:
        baseline.original_role = payload.role
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Account is already a household member") from exc
    await session.refresh(membership)
    logger.info(
        "household_membership_created",
        actor_user_id=str(actor.application_user_id),
        target_user_id=str(user.id),
        household_id=str(household_id),
        previous_role=None,
        resulting_role=payload.role,
    )
    return _membership_read(membership, user)


@router.patch(
    "/households/{household_id}/memberships/{membership_id}",
    response_model=MembershipRead,
)
async def update_membership(
    household_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: MembershipUpdate,
    actor: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.ADMIN))],
    session: AsyncSession = Depends(get_session),
) -> MembershipRead:
    _assert_role_can_be_managed(actor.role, payload.role)
    membership = await _membership_for_update(household_id, membership_id, session)
    _assert_role_can_be_managed(actor.role, membership.role)
    await _reject_inherited_membership_mutation(membership, session)
    if membership.role == HouseholdRole.OWNER and payload.role != HouseholdRole.OWNER:
        await _protect_final_owner(membership, session)
    previous_role = membership.role
    baseline = await _direct_membership_baseline(membership, session)
    if baseline is not None:
        baseline.original_role = payload.role
    membership.role = payload.role
    await session.commit()
    user = await session.get(ApplicationUser, membership.application_user_id)
    assert user is not None
    logger.info(
        "household_membership_updated",
        actor_user_id=str(actor.application_user_id),
        target_user_id=str(user.id),
        household_id=str(household_id),
        previous_role=previous_role,
        resulting_role=payload.role,
    )
    return _membership_read(membership, user)


@router.delete(
    "/households/{household_id}/memberships/{membership_id}",
    status_code=204,
)
async def delete_membership(
    household_id: uuid.UUID,
    membership_id: uuid.UUID,
    actor: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.ADMIN))],
    session: AsyncSession = Depends(get_session),
) -> None:
    membership = await _membership_for_update(household_id, membership_id, session)
    _assert_role_can_be_managed(actor.role, membership.role)
    await _reject_inherited_membership_mutation(membership, session)
    await _protect_final_owner(membership, session)
    previous_role = membership.role
    target_user_id = membership.application_user_id
    baseline = await _direct_membership_baseline(membership, session)
    if baseline is not None:
        baseline.original_role = None
    await session.delete(membership)
    await session.commit()
    logger.info(
        "household_membership_deleted",
        actor_user_id=str(actor.application_user_id),
        target_user_id=str(target_user_id),
        household_id=str(household_id),
        previous_role=previous_role,
        resulting_role=None,
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
