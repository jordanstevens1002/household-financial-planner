import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.logging import get_logger
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
)
from app.purchase_calculations import calculate_feasibility, money
from app.purchase_providers.base import PurchaseContext
from app.purchase_providers.registry import PurchaseProviderError, get_purchase_provider
from app.purchase_schemas import (
    CalculatedCost,
    FeasibilityRead,
    FeasibilityRequest,
    PurchasePlanCreate,
    PurchasePlanRead,
)

router = APIRouter(prefix="/api/v1", tags=["purchase planning"])
logger = get_logger(component="purchases")


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
    session.add_all(
        [
            PurchaseFundingSource(purchase_plan_id=plan.id, **item.model_dump())
            for item in payload.funding_sources
        ]
        + [PurchaseCost(purchase_plan_id=plan.id, **item.model_dump()) for item in payload.costs]
        + [
            PurchaseOwnershipAllocation(purchase_plan_id=plan.id, **item.model_dump())
            for item in payload.ownership
        ]
    )
    await session.commit()
    await session.refresh(plan)
    logger.info("purchase_plan_created", purchase_plan_id=str(plan.id))
    return plan


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
            select(PurchaseFundingSource).where(PurchaseFundingSource.purchase_plan_id == plan.id)
        )
    )
    stored_costs = list(
        await session.scalars(select(PurchaseCost).where(PurchaseCost.purchase_plan_id == plan.id))
    )
    provider_costs: list[CalculatedCost] = []
    assumptions: list[str] = []
    warnings: list[str] = []
    if plan.provider_code is not None:
        try:
            result = get_purchase_provider(plan.provider_code).calculate(
                PurchaseContext(
                    payload.purchase_price,
                    purchase_type.code,
                    plan.target_location,
                    plan.intended_use,
                    plan.target_date,
                    plan.currency,
                ),
                plan.provider_settings,
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
    values = calculate_feasibility(
        payload.purchase_price,
        sum((item.amount for item in costs), Decimal("0")),
        plan.desired_buffer,
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
            "Loan repayment uses a constant principal-and-interest rate.",
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
