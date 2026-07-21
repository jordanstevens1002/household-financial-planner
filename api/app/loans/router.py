"""Loan API routes."""

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
from app.events.router import _event_read
from app.events.schemas import FinancialEventRead
from app.loans.calculations import generate_schedule, minimum_repayment, payments_per_year
from app.loans.schemas import (
    GoalCreate,
    GoalRead,
    LoanCreate,
    LoanEventCreate,
    LoanGroupCreate,
    LoanGroupRead,
    LoanRead,
    LoanScheduleRead,
    RefinanceCreate,
    RefinanceRead,
    TargetCalculationRead,
    TargetCalculationRequest,
)
from app.models import (
    ApplicationUser,
    EventClassification,
    EventType,
    FinancialEvent,
    Goal,
    Household,
    HouseholdMembership,
    HouseholdRole,
    Loan,
    LoanGroup,
    LookupItem,
    Person,
    Property,
)

router = APIRouter(prefix="/api/v1", tags=["loans"])
logger = get_logger(component="loans")

LOAN_EVENT_CODES = {
    "LOAN_RATE_CHANGED",
    "LOAN_REPAYMENT_CHANGED",
    "LOAN_LUMP_SUM_PAID",
    "LOAN_OFFSET_CHANGED",
    "LOAN_REDRAWN",
    "LOAN_REFINANCED",
    "LOAN_TERM_CHANGED",
    "LOAN_INTEREST_ONLY_STARTED",
    "LOAN_INTEREST_ONLY_ENDED",
    "LOAN_CLOSED",
}


async def _loan_with_access(
    loan_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> Loan:
    loan = await session.scalar(
        select(Loan)
        .join(HouseholdMembership, HouseholdMembership.household_id == Loan.household_id)
        .where(Loan.id == loan_id, HouseholdMembership.application_user_id == user.id)
    )
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan not found")
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == loan.household_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    assert membership is not None
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient household role")
    return loan


async def _create_loan_record(
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
        if group is None or group.household_id != household_id:
            raise HTTPException(422, "Loan group must belong to the household")
    values = payload.model_dump()
    values["currency"] = payload.currency or household.currency
    loan = Loan(household_id=household_id, **values)
    session.add(loan)
    await session.flush()
    return loan


@router.get("/households/{household_id}/loans", response_model=list[LoanRead])
async def list_loans(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Loan]:
    return list(await session.scalars(select(Loan).where(Loan.household_id == household_id)))


@router.post(
    "/households/{household_id}/loan-groups", response_model=LoanGroupRead, status_code=201
)
async def create_loan_group(
    household_id: uuid.UUID,
    payload: LoanGroupCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> LoanGroup:
    if payload.property_id is not None:
        property_record = await session.get(Property, payload.property_id)
        if property_record is None or property_record.household_id != household_id:
            raise HTTPException(422, "Loan group property must belong to the household")
    group = LoanGroup(household_id=household_id, **payload.model_dump())
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


@router.post("/households/{household_id}/loans", response_model=LoanRead, status_code=201)
async def create_loan(
    household_id: uuid.UUID,
    payload: LoanCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Loan:
    loan = await _create_loan_record(household_id, payload, session)
    await session.commit()
    await session.refresh(loan)
    return loan


@router.get("/loans/{loan_id}", response_model=LoanRead)
async def get_loan(
    loan_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Loan:
    return await _loan_with_access(loan_id, HouseholdRole.VIEWER, user, session)


def _validate_loan_event(payload: LoanEventCreate, event_type: EventType) -> None:
    if event_type.code not in LOAN_EVENT_CODES:
        raise HTTPException(422, "Loan event type required")
    if event_type.code == "LOAN_RATE_CHANGED" and payload.percentage is None:
        raise HTTPException(422, "LOAN_RATE_CHANGED requires percentage")
    if (
        event_type.code
        in {
            "LOAN_REPAYMENT_CHANGED",
            "LOAN_LUMP_SUM_PAID",
            "LOAN_OFFSET_CHANGED",
            "LOAN_REDRAWN",
        }
        and payload.amount is None
    ):
        raise HTTPException(422, f"{event_type.code} requires amount")
    if event_type.code == "LOAN_TERM_CHANGED":
        term = payload.payload.get("term_months")
        if not isinstance(term, int) or term <= 0:
            raise HTTPException(422, "LOAN_TERM_CHANGED requires positive term_months")


@router.post("/loans/{loan_id}/events", response_model=FinancialEventRead, status_code=201)
async def create_loan_event(
    loan_id: uuid.UUID,
    payload: LoanEventCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialEventRead:
    loan = await _loan_with_access(loan_id, HouseholdRole.EDITOR, user, session)
    event_type = await session.get(EventType, payload.event_type_id)
    if event_type is None or not event_type.is_active:
        raise HTTPException(422, "Active event type required")
    _validate_loan_event(payload, event_type)
    if payload.idempotency_key is not None:
        duplicate = await session.scalar(
            select(FinancialEvent.id).where(
                FinancialEvent.household_id == loan.household_id,
                FinancialEvent.idempotency_key == payload.idempotency_key,
            )
        )
        if duplicate is not None:
            raise HTTPException(409, "Duplicate event idempotency key")
    event = FinancialEvent(
        household_id=loan.household_id,
        loan_id=loan.id,
        event_type_id=payload.event_type_id,
        idempotency_key=payload.idempotency_key,
        effective_at=payload.effective_at,
        amount=payload.amount,
        percentage=payload.percentage,
        payload=payload.payload,
        notes=payload.notes,
        classification=payload.classification,
        is_enabled=payload.is_enabled,
        data_quality_flags=[],
        created_by_user_id=user.id,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    logger.info("loan_event_created", loan_id=str(loan.id), event_type=event_type.code)
    return _event_read(event, event_type)


async def _loan_events(
    loan_id: uuid.UUID, session: AsyncSession
) -> list[tuple[FinancialEvent, str]]:
    rows = (
        await session.execute(
            select(FinancialEvent, EventType.code)
            .join(EventType, EventType.id == FinancialEvent.event_type_id)
            .where(FinancialEvent.loan_id == loan_id, FinancialEvent.is_enabled.is_(True))
            .order_by(
                FinancialEvent.effective_at,
                EventType.priority,
                FinancialEvent.recorded_at,
                FinancialEvent.id,
            )
        )
    ).all()
    return [(event, code) for event, code in rows]


@router.get("/loans/{loan_id}/schedule", response_model=LoanScheduleRead)
async def loan_schedule(
    loan_id: uuid.UUID,
    through_date: date | None = None,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanScheduleRead:
    loan = await _loan_with_access(loan_id, HouseholdRole.VIEWER, user, session)
    events = await _loan_events(loan_id, session)
    try:
        schedule = generate_schedule(loan, events, through_date)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if any(code == "LOAN_OFFSET_CHANGED" for _, code in events):
        try:
            no_offset = generate_schedule(
                loan,
                [(event, code) for event, code in events if code != "LOAN_OFFSET_CHANGED"],
                through_date,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        schedule.interest_saved_vs_no_offset = max(
            Decimal("0"), no_offset.total_interest - schedule.total_interest
        )
    return schedule


@router.post("/loans/{loan_id}/refinance", response_model=RefinanceRead, status_code=201)
async def refinance_loan(
    loan_id: uuid.UUID,
    payload: RefinanceCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RefinanceRead:
    old_loan = await _loan_with_access(loan_id, HouseholdRole.EDITOR, user, session)
    if payload.replacement_loan.opening_balance_date != payload.effective_at.date():
        raise HTTPException(422, "Replacement opening date must equal refinance effective date")
    if payload.replacement_loan.property_id != old_loan.property_id:
        raise HTTPException(422, "Replacement loan must retain the refinanced property")
    event_type = await session.scalar(
        select(EventType).where(EventType.code == "LOAN_REFINANCED", EventType.is_active.is_(True))
    )
    if event_type is None:
        raise HTTPException(422, "Active LOAN_REFINANCED event type required")
    if payload.idempotency_key is not None:
        duplicate = await session.scalar(
            select(FinancialEvent.id).where(
                FinancialEvent.household_id == old_loan.household_id,
                FinancialEvent.idempotency_key == payload.idempotency_key,
            )
        )
        if duplicate is not None:
            raise HTTPException(409, "Duplicate event idempotency key")
    replacement = await _create_loan_record(
        old_loan.household_id, payload.replacement_loan, session
    )
    event = FinancialEvent(
        household_id=old_loan.household_id,
        loan_id=old_loan.id,
        event_type_id=event_type.id,
        idempotency_key=payload.idempotency_key,
        effective_at=payload.effective_at,
        payload={"replacement_loan_id": str(replacement.id)},
        notes=payload.notes,
        classification=EventClassification.OBSERVED,
        is_enabled=True,
        data_quality_flags=[],
        created_by_user_id=user.id,
    )
    session.add(event)
    old_loan.is_active = False
    await session.commit()
    await session.refresh(replacement)
    await session.refresh(event)
    logger.info(
        "loan_refinanced", loan_id=str(old_loan.id), replacement_loan_id=str(replacement.id)
    )
    return RefinanceRead(
        closed_loan_id=old_loan.id,
        replacement_loan=LoanRead.model_validate(replacement),
        refinance_event=_event_read(event, event_type),
    )


@router.post("/households/{household_id}/goals", response_model=GoalRead, status_code=201)
async def create_goal(
    household_id: uuid.UUID,
    payload: GoalCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Goal:
    goal_type = await session.get(LookupItem, payload.goal_type_id)
    if goal_type is None or goal_type.category != "goal_type" or not goal_type.is_active:
        raise HTTPException(422, "Active goal_type lookup required")
    if payload.person_id is not None:
        person = await session.get(Person, payload.person_id)
        if person is None or person.household_id != household_id:
            raise HTTPException(422, "Goal person must belong to the household")
    if payload.property_id is not None:
        property_record = await session.get(Property, payload.property_id)
        if property_record is None or property_record.household_id != household_id:
            raise HTTPException(422, "Goal property must belong to the household")
    if payload.loan_id is not None:
        loan = await session.get(Loan, payload.loan_id)
        if loan is None or loan.household_id != household_id:
            raise HTTPException(422, "Goal loan must belong to the household")
    goal = Goal(household_id=household_id, **payload.model_dump())
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal


@router.get("/households/{household_id}/goals", response_model=list[GoalRead])
async def list_goals(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Goal]:
    return list(
        await session.scalars(
            select(Goal).where(Goal.household_id == household_id).order_by(Goal.priority, Goal.id)
        )
    )


@router.post("/loans/{loan_id}/target-calculation", response_model=TargetCalculationRead)
async def target_calculation(
    loan_id: uuid.UUID,
    payload: TargetCalculationRequest,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> TargetCalculationRead:
    loan = await _loan_with_access(loan_id, HouseholdRole.VIEWER, user, session)
    goal = await session.get(Goal, payload.goal_id)
    if goal is None or goal.household_id != loan.household_id or goal.loan_id != loan.id:
        raise HTTPException(404, "Loan goal not found")
    goal_type = await session.get(LookupItem, goal.goal_type_id)
    if (
        goal_type is None
        or goal_type.code != "MAXIMUM_WEEKLY_REPAYMENT"
        or goal.target_amount is None
    ):
        raise HTTPException(422, "MAXIMUM_WEEKLY_REPAYMENT amount goal required")
    if loan.term_months is None:
        raise HTTPException(422, "A loan term is required for a target repayment calculation")
    events = await _loan_events(loan_id, session)
    partial_schedule = generate_schedule(loan, events, payload.as_of)
    current_balance = partial_schedule.remaining_balance
    schedule = generate_schedule(loan, events)
    elapsed_months = max(
        0,
        (payload.as_of.year - loan.opening_balance_date.year) * 12
        + payload.as_of.month
        - loan.opening_balance_date.month,
    )
    remaining_months = max(1, loan.term_months - elapsed_months)
    periods = max(1, (remaining_months * payments_per_year(loan.repayment_frequency) + 11) // 12)
    current_rate = (
        partial_schedule.entries[-1].annual_interest_rate
        if partial_schedule.entries
        else loan.initial_interest_rate
    )
    required = minimum_repayment(current_balance, current_rate, periods, loan.repayment_frequency)
    weekly_equivalent = (
        required * Decimal(payments_per_year(loan.repayment_frequency)) / Decimal(52)
    )
    return TargetCalculationRead(
        loan_id=loan.id,
        goal_id=goal.id,
        required_repayment=required,
        repayment_frequency=loan.repayment_frequency,
        target_amount=goal.target_amount,
        within_target=weekly_equivalent <= goal.target_amount,
        estimated_payoff_date=schedule.payoff_date,
    )
