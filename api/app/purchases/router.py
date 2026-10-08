"""Purchase-planning API routes."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.core.logging import get_logger
from app.models import (
    ApplicationUser,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    OwnerType,
    Person,
    PurchaseCost,
    PurchaseFundingSource,
    PurchaseOwnershipAllocation,
    PurchasePlan,
    PurchasePlanChildRevision,
)
from app.purchases.calculations import calculate_feasibility, money
from app.purchases.providers.base import PurchaseContext
from app.purchases.providers.registry import (
    PurchaseProviderError,
    get_purchase_provider,
    get_registry,
)
from app.purchases.schemas import (
    CalculatedCost,
    ChildRetire,
    CostCreate,
    CostRead,
    CostUpdate,
    FeasibilityRead,
    FeasibilityRequest,
    FundingSourceCreate,
    FundingSourceRead,
    FundingSourceUpdate,
    OwnershipCreate,
    OwnershipSetReplace,
    PurchaseOwnershipRead,
    PurchasePlanCreate,
    PurchasePlanDetail,
    PurchasePlanRead,
    PurchaseProviderRead,
)

router = APIRouter(prefix="/api/v1", tags=["purchase planning"])
logger = get_logger(component="purchases")


@router.get("/purchase-providers", response_model=list[PurchaseProviderRead])
async def list_purchase_providers(
    _: ApplicationUser = Depends(current_user),
) -> list[PurchaseProviderRead]:
    return [
        PurchaseProviderRead(code=provider.code, display_name=provider.display_name)
        for provider in get_registry().providers()
    ]


async def _plan_with_access(
    plan_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> PurchasePlan:
    row = (
        await session.execute(
            select(PurchasePlan, HouseholdMembership)
            .join(
                HouseholdMembership, HouseholdMembership.household_id == PurchasePlan.household_id
            )
            .where(
                PurchasePlan.id == plan_id,
                HouseholdMembership.application_user_id == user.id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Purchase plan not found")
    plan, membership = row
    assert isinstance(plan, PurchasePlan)
    assert isinstance(membership, HouseholdMembership)
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(403, "Insufficient household role")
    return plan


def _funding_snapshot(item: PurchaseFundingSource) -> dict[str, object]:
    return {
        "id": str(item.id),
        "display_name": item.display_name,
        "source_type": item.source_type,
        "amount": str(item.amount),
        "available_date": item.available_date.isoformat(),
        "is_borrowed": item.is_borrowed,
        "notes": item.notes,
        "is_active": item.is_active,
        "revision": item.revision,
    }


def _cost_snapshot(item: PurchaseCost) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "display_name": item.display_name,
        "amount": str(item.amount),
        "is_estimate": item.is_estimate,
        "is_active": item.is_active,
        "revision": item.revision,
    }


def _ownership_snapshot(item: PurchaseOwnershipAllocation) -> dict[str, object]:
    return {
        "id": str(item.id),
        "owner_type": item.owner_type.value,
        "person_id": str(item.person_id) if item.person_id else None,
        "external_owner_name": item.external_owner_name,
        "ownership_percentage": str(item.ownership_percentage),
        "is_active": item.is_active,
        "revision": item.revision,
    }


def _revision(
    plan: PurchasePlan,
    user: ApplicationUser,
    child_type: str,
    action: str,
    previous: dict[str, object] | list[dict[str, object]] | None,
    resulting: dict[str, object] | list[dict[str, object]] | None,
    child_id: uuid.UUID | None = None,
) -> PurchasePlanChildRevision:
    return PurchasePlanChildRevision(
        purchase_plan_id=plan.id,
        household_id=plan.household_id,
        actor_user_id=user.id,
        child_type=child_type,
        child_id=child_id,
        action=action,
        previous_state=previous,
        resulting_state=resulting,
    )


async def _validate_ownership_people(
    plan: PurchasePlan, ownership: list[OwnershipCreate], session: AsyncSession
) -> None:
    person_ids = {item.person_id for item in ownership if item.person_id is not None}
    if not person_ids:
        return
    found = set(
        await session.scalars(
            select(Person.id).where(
                Person.id.in_(person_ids), Person.household_id == plan.household_id
            )
        )
    )
    if found != person_ids:
        raise HTTPException(422, "Ownership people must belong to the household")


async def _funding_with_lock(
    plan: PurchasePlan, child_id: uuid.UUID, session: AsyncSession
) -> PurchaseFundingSource:
    item = await session.scalar(
        select(PurchaseFundingSource)
        .where(
            PurchaseFundingSource.id == child_id,
            PurchaseFundingSource.purchase_plan_id == plan.id,
            PurchaseFundingSource.is_active.is_(True),
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(404, "Funding source not found")
    return item


async def _cost_with_lock(
    plan: PurchasePlan, child_id: uuid.UUID, session: AsyncSession
) -> PurchaseCost:
    item = await session.scalar(
        select(PurchaseCost)
        .where(
            PurchaseCost.id == child_id,
            PurchaseCost.purchase_plan_id == plan.id,
            PurchaseCost.is_active.is_(True),
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(404, "Purchase cost not found")
    return item


@router.get("/households/{household_id}/purchase-plans", response_model=list[PurchasePlanRead])
async def list_purchase_plans(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[PurchasePlan]:
    return list(
        await session.scalars(select(PurchasePlan).where(PurchasePlan.household_id == household_id))
    )


@router.post(
    "/households/{household_id}/purchase-plans",
    response_model=PurchasePlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_plan(
    household_id: uuid.UUID,
    payload: PurchasePlanCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PurchasePlan:
    household = await session.get(Household, household_id)
    assert household is not None
    purchase_type = await session.get(LookupItem, payload.purchase_type_id)
    if (
        purchase_type is None
        or purchase_type.category != "purchase_type"
        or not purchase_type.is_active
    ):
        raise HTTPException(422, "Active purchase_type lookup required")
    provider_settings = payload.provider_settings
    if payload.provider_code is not None:
        try:
            provider_settings = get_purchase_provider(payload.provider_code).validate_settings(
                provider_settings
            )
        except (PurchaseProviderError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
    for owner in payload.ownership:
        if owner.person_id is not None:
            person = await session.get(Person, owner.person_id)
            if person is None or person.household_id != household_id:
                raise HTTPException(422, "Ownership person must belong to the household")
        if owner.owner_type == OwnerType.PERSON and owner.person_id is None:
            raise HTTPException(422, "PERSON ownership requires person_id")
    values = payload.model_dump(exclude={"funding_sources", "costs", "ownership"})
    values["currency"] = payload.currency or household.currency
    values["provider_settings"] = provider_settings
    plan = PurchasePlan(household_id=household_id, **values)
    session.add(plan)
    await session.flush()
    funding = [
        PurchaseFundingSource(purchase_plan_id=plan.id, **item.model_dump())
        for item in payload.funding_sources
    ]
    costs = [PurchaseCost(purchase_plan_id=plan.id, **item.model_dump()) for item in payload.costs]
    ownership = [
        PurchaseOwnershipAllocation(purchase_plan_id=plan.id, **item.model_dump())
        for item in payload.ownership
    ]
    session.add_all(funding)
    session.add_all(costs)
    session.add_all(ownership)
    await session.flush()
    session.add_all(
        [
            _revision(plan, user, "FUNDING", "CREATED", None, _funding_snapshot(item), item.id)
            for item in funding
        ]
        + [
            _revision(plan, user, "COST", "CREATED", None, _cost_snapshot(item), item.id)
            for item in costs
        ]
        + (
            [
                _revision(
                    plan,
                    user,
                    "OWNERSHIP",
                    "REPLACED",
                    [],
                    [_ownership_snapshot(item) for item in ownership],
                )
            ]
            if ownership
            else []
        )
    )
    await session.commit()
    await session.refresh(plan)
    logger.info(
        "purchase_plan_created",
        actor_user_id=str(user.id),
        household_id=str(household_id),
        purchase_plan_id=str(plan.id),
    )
    return plan


@router.get("/purchase-plans/{plan_id}", response_model=PurchasePlanDetail)
async def get_purchase_plan(
    plan_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PurchasePlanDetail:
    plan = await _plan_with_access(plan_id, HouseholdRole.VIEWER, user, session)
    funding = list(
        await session.scalars(
            select(PurchaseFundingSource).where(
                PurchaseFundingSource.purchase_plan_id == plan.id,
                PurchaseFundingSource.is_active.is_(True),
            )
        )
    )
    costs = list(
        await session.scalars(
            select(PurchaseCost).where(
                PurchaseCost.purchase_plan_id == plan.id, PurchaseCost.is_active.is_(True)
            )
        )
    )
    ownership = list(
        await session.scalars(
            select(PurchaseOwnershipAllocation).where(
                PurchaseOwnershipAllocation.purchase_plan_id == plan.id,
                PurchaseOwnershipAllocation.is_active.is_(True),
            )
        )
    )
    return PurchasePlanDetail(
        **PurchasePlanRead.model_validate(plan).model_dump(),
        funding_sources=[FundingSourceRead.model_validate(item) for item in funding],
        costs=[CostRead.model_validate(item) for item in costs],
        ownership=[PurchaseOwnershipRead.model_validate(item) for item in ownership],
    )


@router.post(
    "/purchase-plans/{plan_id}/funding-sources",
    response_model=FundingSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_funding_source(
    plan_id: uuid.UUID,
    payload: FundingSourceCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PurchaseFundingSource:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    item = PurchaseFundingSource(purchase_plan_id=plan.id, **payload.model_dump())
    session.add(item)
    await session.flush()
    session.add(_revision(plan, user, "FUNDING", "CREATED", None, _funding_snapshot(item), item.id))
    await session.commit()
    logger.info(
        "purchase_funding_source_created",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        child_id=str(item.id),
        revision=item.revision,
    )
    return item


@router.patch(
    "/purchase-plans/{plan_id}/funding-sources/{child_id}",
    response_model=FundingSourceRead,
)
async def update_funding_source(
    plan_id: uuid.UUID,
    child_id: uuid.UUID,
    payload: FundingSourceUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PurchaseFundingSource:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    item = await _funding_with_lock(plan, child_id, session)
    if item.revision != payload.expected_revision:
        raise HTTPException(409, "Funding source changed; reload before correcting it")
    previous = _funding_snapshot(item)
    changes = payload.model_dump(exclude={"expected_revision"}, exclude_unset=True)
    if all(getattr(item, field) == value for field, value in changes.items()):
        raise HTTPException(422, "Funding source correction does not change any values")
    for field, value in changes.items():
        setattr(item, field, value)
    item.revision += 1
    resulting = _funding_snapshot(item)
    session.add(_revision(plan, user, "FUNDING", "CORRECTED", previous, resulting, item.id))
    await session.commit()
    logger.info(
        "purchase_funding_source_corrected",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        child_id=str(item.id),
        revision=item.revision,
    )
    return item


@router.delete(
    "/purchase-plans/{plan_id}/funding-sources/{child_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def retire_funding_source(
    plan_id: uuid.UUID,
    child_id: uuid.UUID,
    payload: ChildRetire,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    item = await _funding_with_lock(plan, child_id, session)
    if item.revision != payload.expected_revision:
        raise HTTPException(409, "Funding source changed; reload before removing it")
    previous = _funding_snapshot(item)
    item.is_active = False
    item.revision += 1
    session.add(
        _revision(plan, user, "FUNDING", "RETIRED", previous, _funding_snapshot(item), item.id)
    )
    await session.commit()
    logger.info(
        "purchase_funding_source_retired",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        child_id=str(item.id),
        revision=item.revision,
    )


@router.post(
    "/purchase-plans/{plan_id}/costs",
    response_model=CostRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_cost(
    plan_id: uuid.UUID,
    payload: CostCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PurchaseCost:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    item = PurchaseCost(purchase_plan_id=plan.id, **payload.model_dump())
    session.add(item)
    await session.flush()
    session.add(_revision(plan, user, "COST", "CREATED", None, _cost_snapshot(item), item.id))
    await session.commit()
    logger.info(
        "purchase_cost_created",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        child_id=str(item.id),
        revision=item.revision,
    )
    return item


@router.patch("/purchase-plans/{plan_id}/costs/{child_id}", response_model=CostRead)
async def update_cost(
    plan_id: uuid.UUID,
    child_id: uuid.UUID,
    payload: CostUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PurchaseCost:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    item = await _cost_with_lock(plan, child_id, session)
    if item.revision != payload.expected_revision:
        raise HTTPException(409, "Purchase cost changed; reload before correcting it")
    previous = _cost_snapshot(item)
    changes = payload.model_dump(exclude={"expected_revision"}, exclude_unset=True)
    if all(getattr(item, field) == value for field, value in changes.items()):
        raise HTTPException(422, "Purchase cost correction does not change any values")
    for field, value in changes.items():
        setattr(item, field, value)
    item.revision += 1
    session.add(_revision(plan, user, "COST", "CORRECTED", previous, _cost_snapshot(item), item.id))
    await session.commit()
    logger.info(
        "purchase_cost_corrected",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        child_id=str(item.id),
        revision=item.revision,
    )
    return item


@router.delete("/purchase-plans/{plan_id}/costs/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_cost(
    plan_id: uuid.UUID,
    child_id: uuid.UUID,
    payload: ChildRetire,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    item = await _cost_with_lock(plan, child_id, session)
    if item.revision != payload.expected_revision:
        raise HTTPException(409, "Purchase cost changed; reload before removing it")
    previous = _cost_snapshot(item)
    item.is_active = False
    item.revision += 1
    session.add(_revision(plan, user, "COST", "RETIRED", previous, _cost_snapshot(item), item.id))
    await session.commit()
    logger.info(
        "purchase_cost_retired",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        child_id=str(item.id),
        revision=item.revision,
    )


@router.put("/purchase-plans/{plan_id}/ownership", response_model=list[PurchaseOwnershipRead])
async def replace_ownership(
    plan_id: uuid.UUID,
    payload: OwnershipSetReplace,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PurchaseOwnershipAllocation]:
    plan = await _plan_with_access(plan_id, HouseholdRole.EDITOR, user, session)
    await session.scalar(
        select(PurchasePlan.id).where(PurchasePlan.id == plan.id).with_for_update()
    )
    existing = list(
        await session.scalars(
            select(PurchaseOwnershipAllocation).where(
                PurchaseOwnershipAllocation.purchase_plan_id == plan.id,
                PurchaseOwnershipAllocation.is_active.is_(True),
            )
        )
    )
    if {item.id for item in existing} != set(payload.expected_revision_ids):
        raise HTTPException(409, "Ownership changed; reload before replacing it")
    await _validate_ownership_people(plan, payload.ownership, session)
    previous = [_ownership_snapshot(item) for item in existing]
    for item in existing:
        item.is_active = False
        item.revision += 1
    resulting_items = [
        PurchaseOwnershipAllocation(purchase_plan_id=plan.id, **item.model_dump())
        for item in payload.ownership
    ]
    session.add_all(resulting_items)
    await session.flush()
    resulting = [_ownership_snapshot(item) for item in resulting_items]
    session.add(_revision(plan, user, "OWNERSHIP", "REPLACED", previous, resulting))
    await session.commit()
    logger.info(
        "purchase_ownership_replaced",
        actor_user_id=str(user.id),
        household_id=str(plan.household_id),
        purchase_plan_id=str(plan.id),
        previous_ids=[item["id"] for item in previous],
        resulting_ids=[item["id"] for item in resulting],
    )
    return resulting_items


@router.post("/purchase-plans/{plan_id}/calculate", response_model=FeasibilityRead)
async def calculate_purchase_plan(
    plan_id: uuid.UUID,
    payload: FeasibilityRequest,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FeasibilityRead:
    plan = await _plan_with_access(plan_id, HouseholdRole.VIEWER, user, session)
    purchase_type = await session.get(LookupItem, plan.purchase_type_id)
    assert purchase_type is not None
    funding = list(
        await session.scalars(
            select(PurchaseFundingSource).where(
                PurchaseFundingSource.purchase_plan_id == plan.id,
                PurchaseFundingSource.is_active.is_(True),
            )
        )
    )
    stored_costs = list(
        await session.scalars(
            select(PurchaseCost).where(
                PurchaseCost.purchase_plan_id == plan.id,
                PurchaseCost.is_active.is_(True),
            )
        )
    )
    provider_costs: list[CalculatedCost] = []
    assumptions: list[str] = []
    warnings: list[str] = []
    if plan.provider_code is not None:
        try:
            provider = get_purchase_provider(plan.provider_code)
            provider_settings = (
                plan.provider_settings
                if payload.provider_settings is None
                else provider.validate_settings(payload.provider_settings)
            )
            result = provider.calculate(
                PurchaseContext(
                    payload.purchase_price,
                    purchase_type.code,
                    plan.target_location,
                    plan.intended_use,
                    plan.target_date,
                    plan.currency,
                ),
                provider_settings,
            )
        except (PurchaseProviderError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        provider_costs = [
            CalculatedCost(**item.__dict__, source=plan.provider_code) for item in result.costs
        ]
        assumptions.extend(result.assumptions)
        warnings.extend(result.warnings)
    costs = [
        CalculatedCost(
            code=item.code, display_name=item.display_name, amount=item.amount, source="USER"
        )
        for item in stored_costs
    ] + provider_costs
    available = [item for item in funding if item.available_date <= plan.target_date]
    equity = sum((item.amount for item in available if not item.is_borrowed), Decimal("0"))
    borrowed = sum((item.amount for item in available if item.is_borrowed), Decimal("0"))
    desired_buffer = (
        plan.desired_buffer if payload.desired_buffer is None else payload.desired_buffer
    )
    values = calculate_feasibility(
        payload.purchase_price,
        sum((item.amount for item in costs), Decimal("0")),
        desired_buffer,
        equity,
        borrowed,
        payload.maximum_additional_borrowing,
        payload.annual_interest_rate,
        payload.loan_term_years,
        payload.current_monthly_surplus,
        plan.max_lvr,
        plan.minimum_monthly_surplus,
    )
    assumptions.extend(
        [
            "Only funding available by the target date is included.",
            (
                "The calculation includes a desired post-purchase buffer of "
                f"{desired_buffer} {plan.currency}."
            ),
            (
                "Loan repayment uses a constant principal-and-interest rate of "
                f"{payload.annual_interest_rate}% over {payload.loan_term_years} years."
            ),
            (
                "Affordability starts from the explicitly supplied monthly surplus of "
                f"{payload.current_monthly_surplus} {plan.currency}."
            ),
            (
                "Additional borrowing is limited to the explicitly supplied maximum of "
                f"{payload.maximum_additional_borrowing} {plan.currency}."
            ),
        ]
    )
    return FeasibilityRead(
        purchase_plan_id=plan.id,
        calculation_date=date.today(),
        currency=plan.currency,
        purchase_price=money(payload.purchase_price),
        costs=costs,
        available_equity_funding=values.equity_funding,
        existing_borrowed_funding=values.borrowed_funding,
        additional_loan_required=values.additional_loan,
        total_debt_funding=values.total_debt,
        monthly_loan_repayment=values.monthly_repayment,
        projected_monthly_surplus=values.projected_monthly_surplus,
        lvr=values.lvr,
        funding_gap=values.funding_gap,
        required_total=values.required_total,
        is_feasible=not values.failed_thresholds,
        failed_thresholds=values.failed_thresholds,
        assumptions_used=assumptions,
        warnings=warnings,
    )
