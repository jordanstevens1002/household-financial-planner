"""Rental and property-expense API routes."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import current_user
from app.core.logging import get_logger
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
from app.properties.router import _property_with_access, _validate_lookup
from app.rental.calculations import daily_amount, inclusive_dates, money
from app.rental.schemas import (
    PropertyCashflowRead,
    PropertyExpenseCreate,
    PropertyExpenseRead,
    PropertyExpenseUpdate,
    RentalProfileCreate,
    RentalProfileRead,
    RentalProfileUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["rental"])
logger = get_logger(component="rental")


class EffectiveRecord(Protocol):
    effective_from: date
    effective_to: date | None


async def _validate_profile_overlap(
    property_id: uuid.UUID,
    payload: RentalProfileCreate,
    session: AsyncSession,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    end = payload.effective_to or date.max
    query = select(RentalProfile.id).where(
        RentalProfile.property_id == property_id,
        RentalProfile.effective_from <= end,
        or_(
            RentalProfile.effective_to.is_(None),
            RentalProfile.effective_to >= payload.effective_from,
        ),
    )
    if exclude_id is not None:
        query = query.where(RentalProfile.id != exclude_id)
    existing = list(await session.scalars(query))
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


@router.patch(
    "/properties/{property_id}/rental-profiles/{profile_id}",
    response_model=RentalProfileRead,
)
async def correct_rental_profile(
    property_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: RentalProfileUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RentalProfile:
    property_record = await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    record = await session.get(RentalProfile, profile_id)
    if record is None or record.property_id != property_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rental arrangement not found")
    previous_effective_to = record.effective_to
    values = payload.model_dump(exclude_unset=True)
    candidate_values = {
        **RentalProfileRead.model_validate(record).model_dump(exclude={"id", "property_id"}),
        **values,
    }
    candidate = RentalProfileCreate.model_validate(candidate_values)
    await _validate_profile_overlap(property_id, candidate, session, exclude_id=profile_id)
    for field, value in values.items():
        setattr(record, field, value)
    await session.commit()
    await session.refresh(record)
    logger.info(
        "rental_profile_corrected",
        actor_user_id=str(user.id),
        household_id=str(property_record.household_id),
        property_id=str(property_id),
        profile_id=str(profile_id),
        changed_fields=sorted(values),
        previous_effective_to=(
            previous_effective_to.isoformat() if previous_effective_to else None
        ),
        resulting_effective_to=(record.effective_to.isoformat() if record.effective_to else None),
    )
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
            .where(
                PropertyExpense.property_id == property_id,
                PropertyExpense.superseded_at.is_(None),
                PropertyExpense.deleted_at.is_(None),
            )
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
    property_record = await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    await _validate_lookup(payload.expense_type_id, "property_expense_type", session)
    record = PropertyExpense(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.info(
        "property_expense_created",
        actor_user_id=str(user.id),
        household_id=str(property_record.household_id),
        property_id=str(property_id),
        expense_id=str(record.id),
    )
    return record


async def _property_expense(
    property_id: uuid.UUID,
    expense_id: uuid.UUID,
    session: AsyncSession,
) -> PropertyExpense:
    expense = await session.scalar(
        select(PropertyExpense)
        .where(
            PropertyExpense.id == expense_id,
            PropertyExpense.property_id == property_id,
            PropertyExpense.superseded_at.is_(None),
            PropertyExpense.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property expense not found")
    return expense


def _expense_snapshot(expense: PropertyExpense) -> dict[str, object]:
    return {
        "id": str(expense.id),
        "expense_type_id": str(expense.expense_type_id),
        "display_name": expense.display_name,
        "amount": str(expense.amount),
        "frequency": expense.frequency.value,
        "effective_from": expense.effective_from.isoformat(),
        "effective_to": expense.effective_to.isoformat() if expense.effective_to else None,
        "is_rental_expense": expense.is_rental_expense,
        "notes": expense.notes,
    }


@router.patch(
    "/properties/{property_id}/expenses/{expense_id}",
    response_model=PropertyExpenseRead,
)
async def update_property_expense(
    property_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: PropertyExpenseUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyExpense:
    property_record = await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    expense = await _property_expense(property_id, expense_id, session)
    values = payload.model_dump(exclude_unset=True)
    candidate_values = {
        **PropertyExpenseRead.model_validate(expense).model_dump(exclude={"id", "property_id"}),
        **values,
    }
    candidate = PropertyExpenseCreate.model_validate(candidate_values)
    if candidate.expense_type_id != expense.expense_type_id:
        await _validate_lookup(candidate.expense_type_id, "property_expense_type", session)
    before = _expense_snapshot(expense)
    changed_at = datetime.now(UTC)
    expense.superseded_at = changed_at
    replacement = PropertyExpense(
        property_id=property_id,
        replaces_id=expense.id,
        **candidate.model_dump(),
    )
    session.add(replacement)
    await session.commit()
    await session.refresh(replacement)
    logger.info(
        "property_expense_updated",
        actor_user_id=str(user.id),
        household_id=str(property_record.household_id),
        property_id=str(property_id),
        expense_id=str(replacement.id),
        replaces_expense_id=str(expense_id),
        changed_fields=sorted(values),
        before=before,
        after=_expense_snapshot(replacement),
    )
    return replacement


@router.delete(
    "/properties/{property_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_property_expense(
    property_id: uuid.UUID,
    expense_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    property_record = await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    expense = await _property_expense(property_id, expense_id, session)
    before = _expense_snapshot(expense)
    deleted_at = datetime.now(UTC)
    expense.deleted_at = deleted_at
    await session.commit()
    logger.info(
        "property_expense_deleted",
        actor_user_id=str(user.id),
        household_id=str(property_record.household_id),
        property_id=str(property_id),
        expense_id=str(expense_id),
        before=before,
        deleted_at=deleted_at.isoformat(),
    )


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
            select(PropertyExpense).where(
                PropertyExpense.property_id == property_id,
                PropertyExpense.superseded_at.is_(None),
                PropertyExpense.deleted_at.is_(None),
            )
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
    if profiles or any(item.frequency != PaymentFrequency.ONCE for item in expenses):
        warnings.add("Recurring amounts use a 365-day planning year for daily allocation")
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
        partial_owner_rental = bool(
            status_item
            and status_item.is_occupied_by_household
            and any(profile.rental_share_percentage < Decimal("100") for profile in active_profiles)
        )
        generates_rent = (
            bool(status_item and status_item.generates_rental_income) or partial_owner_rental
        )
        if generates_rent and not active_profiles:
            warnings.add("Rental status is active without an effective rental profile")
        if generates_rent and active_profiles:
            rental_days += 1
            for profile in active_profiles:
                daily_charged = daily_amount(profile.charged_rent_amount, profile.frequency)
                daily_market = (
                    daily_amount(profile.market_rent_amount, profile.frequency)
                    if profile.market_rent_amount is not None
                    else daily_charged
                )
                daily_vacancy = (
                    daily_charged * profile.vacancy_rate / Decimal("100")
                    if status_item and (status_item.applies_vacancy or partial_owner_rental)
                    else Decimal("0")
                )
                daily_management = (
                    (daily_charged - daily_vacancy) * profile.management_fee_rate / Decimal("100")
                    if status_item and (status_item.applies_management_fee or partial_owner_rental)
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
                status_item and (status_item.applies_rental_expenses or partial_owner_rental)
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
