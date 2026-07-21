import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import current_user
from app.logging import get_logger
from app.models import (
    ApplicationUser,
    EventType,
    FinancialEvent,
    HouseholdRole,
    LookupItem,
    PaymentFrequency,
    PropertyBaseline,
    PropertyExpense,
    RentalProfile,
)
from app.properties import _property_with_access, _validate_lookup
from app.rental_calculations import daily_amount, inclusive_dates, money
from app.rental_schemas import (
    PropertyCashflowRead,
    PropertyExpenseCreate,
    PropertyExpenseRead,
    RentalProfileCreate,
    RentalProfileRead,
)

router = APIRouter(prefix="/api/v1", tags=["rental"])
logger = get_logger(component="rental")


class EffectiveRecord(Protocol):
    effective_from: date
    effective_to: date | None


async def _validate_profile_overlap(
    property_id: uuid.UUID, payload: RentalProfileCreate, session: AsyncSession
) -> None:
    end = payload.effective_to or date.max
    existing = list(
        await session.scalars(
            select(RentalProfile.id).where(
                RentalProfile.property_id == property_id,
                RentalProfile.effective_from <= end,
                or_(
                    RentalProfile.effective_to.is_(None),
                    RentalProfile.effective_to >= payload.effective_from,
                ),
            )
        )
    )
    if not existing:
        return
    profiles = list(
        await session.scalars(select(RentalProfile).where(RentalProfile.id.in_(existing)))
    )
    if any(item.display_name.casefold() == payload.display_name.casefold() for item in profiles):
        raise HTTPException(409, "Dates overlap for the same named rental portion")
    boundaries = {payload.effective_from}
    for item in profiles:
        boundaries.add(max(item.effective_from, payload.effective_from))
        if item.effective_to is not None and item.effective_to < end:
            boundaries.add(item.effective_to + timedelta(days=1))
    for boundary in boundaries:
        if boundary > end:
            continue
        share = payload.rental_share_percentage + sum(
            (
                item.rental_share_percentage
                for item in profiles
                if item.effective_from <= boundary
                and (item.effective_to is None or item.effective_to >= boundary)
            ),
            Decimal("0"),
        )
        if share > Decimal("100"):
            raise HTTPException(422, "Concurrent rental portions cannot exceed 100% total share")


@router.get("/properties/{property_id}/rental-profiles", response_model=list[RentalProfileRead])
async def list_rental_profiles(
    property_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RentalProfile]:
    await _property_with_access(property_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(RentalProfile)
            .where(RentalProfile.property_id == property_id)
            .order_by(RentalProfile.effective_from)
        )
    )


@router.post(
    "/properties/{property_id}/rental-profiles",
    response_model=RentalProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rental_profile(
    property_id: uuid.UUID,
    payload: RentalProfileCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RentalProfile:
    await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    await _validate_profile_overlap(property_id, payload, session)
    record = RentalProfile(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.info("rental_profile_created", property_id=str(property_id), profile_id=str(record.id))
    return record


@router.get("/properties/{property_id}/expenses", response_model=list[PropertyExpenseRead])
async def list_property_expenses(
    property_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PropertyExpense]:
    await _property_with_access(property_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(PropertyExpense)
            .where(PropertyExpense.property_id == property_id)
            .order_by(PropertyExpense.effective_from)
        )
    )


@router.post(
    "/properties/{property_id}/expenses",
    response_model=PropertyExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_property_expense(
    property_id: uuid.UUID,
    payload: PropertyExpenseCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyExpense:
    await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    await _validate_lookup(payload.expense_type_id, "property_expense_type", session)
    record = PropertyExpense(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.info("property_expense_created", property_id=str(property_id), expense_id=str(record.id))
    return record


async def _cashflow_inputs(
    property_id: uuid.UUID, to_date: date, session: AsyncSession
) -> tuple[
    list[RentalProfile],
    list[PropertyExpense],
    list[PropertyBaseline],
    list[tuple[FinancialEvent, EventType]],
    dict[uuid.UUID, LookupItem],
]:
    profiles = list(
        await session.scalars(select(RentalProfile).where(RentalProfile.property_id == property_id))
    )
    expenses = list(
        await session.scalars(
            select(PropertyExpense).where(PropertyExpense.property_id == property_id)
        )
    )
    baselines = list(
        await session.scalars(
            select(PropertyBaseline)
            .where(
                PropertyBaseline.property_id == property_id,
                PropertyBaseline.baseline_date <= to_date,
            )
            .order_by(PropertyBaseline.baseline_date)
        )
    )
    result = await session.execute(
        select(FinancialEvent, EventType)
        .join(EventType, EventType.id == FinancialEvent.event_type_id)
        .where(
            FinancialEvent.property_id == property_id,
            FinancialEvent.is_enabled.is_(True),
            EventType.code == "PROPERTY_STATUS_CHANGED",
            FinancialEvent.effective_at
            < datetime.combine(to_date + timedelta(days=1), time.min, UTC),
        )
        .order_by(FinancialEvent.effective_at, EventType.priority, FinancialEvent.id)
    )
    rows = [(row[0], row[1]) for row in result]
    status_ids = {baseline.status_id for baseline in baselines}
    for event, _ in rows:
        try:
            status_ids.add(uuid.UUID(str(event.payload["status_id"])))
        except KeyError, TypeError, ValueError:
            continue
    statuses = {
        item.id: item
        for item in await session.scalars(select(LookupItem).where(LookupItem.id.in_(status_ids)))
    }
    return profiles, expenses, baselines, rows, statuses


def _active[T: EffectiveRecord](records: list[T], on_date: date) -> list[T]:
    return [
        item
        for item in records
        if item.effective_from <= on_date
        and (item.effective_to is None or item.effective_to >= on_date)
    ]


@router.get("/properties/{property_id}/cashflow", response_model=PropertyCashflowRead)
async def property_cashflow(
    property_id: uuid.UUID,
    from_date: date = Query(),
    to_date: date = Query(),
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyCashflowRead:
    if to_date < from_date:
        raise HTTPException(422, "to_date must not precede from_date")
    if (to_date - from_date).days > 3660:
        raise HTTPException(422, "cashflow range cannot exceed ten years")
    property_record = await _property_with_access(property_id, HouseholdRole.VIEWER, user, session)
    profiles, expenses, baselines, events, statuses = await _cashflow_inputs(
        property_id, to_date, session
    )
    current_status = await session.get(LookupItem, property_record.current_status_id)
    gross = vacancy = management = letting = costs = market = charged = Decimal("0")
    rental_days = 0
    warnings: set[str] = set()
    for on_date in inclusive_dates(from_date, to_date):
        baseline = next(
            (item for item in reversed(baselines) if item.baseline_date <= on_date), None
        )
        status_item = statuses.get(baseline.status_id) if baseline else current_status
        baseline_date = baseline.baseline_date if baseline else date.min
        for event, _ in events:
            if baseline_date <= event.effective_at.date() <= on_date:
                try:
                    status_item = statuses.get(
                        uuid.UUID(str(event.payload["status_id"])), status_item
                    )
                except KeyError, TypeError, ValueError:
                    continue
        active_profiles = _active(profiles, on_date)
        generates_rent = bool(status_item and status_item.generates_rental_income)
        if generates_rent and not active_profiles:
            warnings.add("Rental status is active without an effective rental profile")
        if generates_rent and active_profiles:
            rental_days += 1
            for profile in active_profiles:
                share = profile.rental_share_percentage / Decimal("100")
                daily_charged = daily_amount(profile.charged_rent_amount, profile.frequency) * share
                daily_market = (
                    daily_amount(profile.market_rent_amount, profile.frequency) * share
                    if profile.market_rent_amount is not None
                    else daily_charged
                )
                daily_vacancy = (
                    daily_charged * profile.vacancy_rate / Decimal("100")
                    if status_item and status_item.applies_vacancy
                    else Decimal("0")
                )
                daily_management = (
                    (daily_charged - daily_vacancy) * profile.management_fee_rate / Decimal("100")
                    if status_item and status_item.applies_management_fee
                    else Decimal("0")
                )
                gross += daily_charged
                market += daily_market
                charged += daily_charged
                vacancy += daily_vacancy
                management += daily_management
                if profile.letting_fee is not None and profile.effective_from == on_date:
                    letting += profile.letting_fee
        for expense in _active(expenses, on_date):
            if expense.is_rental_expense and not (
                status_item and status_item.applies_rental_expenses
            ):
                continue
            if expense.frequency == PaymentFrequency.ONCE:
                if expense.effective_from == on_date:
                    costs += expense.amount
            else:
                costs += daily_amount(expense.amount, expense.frequency)
    gross, vacancy, management, letting, costs, market, charged = map(
        money, (gross, vacancy, management, letting, costs, market, charged)
    )
    return PropertyCashflowRead(
        property_id=property_id,
        from_date=from_date,
        to_date=to_date,
        currency=property_record.default_currency,
        gross_rent=gross,
        vacancy_cost=vacancy,
        management_fee=management,
        letting_fees=letting,
        property_expenses=costs,
        net_cashflow=money(gross - vacancy - management - letting - costs),
        market_rent_equivalent=market,
        charged_rent_equivalent=charged,
        rent_difference=money(charged - market),
        rental_days=rental_days,
        warnings=sorted(warnings),
    )
