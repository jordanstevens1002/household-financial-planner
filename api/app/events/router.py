"""Financial event API routes."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.core.logging import get_logger
from app.events.schemas import (
    EventToggle,
    EventTypeRead,
    FinancialEventCreate,
    FinancialEventRead,
    PlannedEventUpdate,
    ResolvedPropertyState,
    TimelineRead,
)
from app.events.timeline import apply_property_event, event_quality_flags, temporal_position
from app.models import (
    ApplicationUser,
    EventClassification,
    EventType,
    FinancialEvent,
    HouseholdMembership,
    HouseholdRole,
    Loan,
    LookupItem,
    Person,
    Property,
    PropertyBaseline,
)

router = APIRouter(prefix="/api/v1", tags=["events"])
logger = get_logger(component="events")


def _event_read(event: FinancialEvent, event_type: EventType) -> FinancialEventRead:
    return FinancialEventRead(
        id=event.id,
        household_id=event.household_id,
        event_type_id=event.event_type_id,
        idempotency_key=event.idempotency_key,
        event_type_code=event_type.code,
        event_priority=event_type.priority,
        effective_at=event.effective_at,
        recorded_at=event.recorded_at,
        property_id=event.property_id,
        person_id=event.person_id,
        loan_id=event.loan_id,
        amount=event.amount,
        percentage=event.percentage,
        payload=event.payload,
        notes=event.notes,
        classification=event.classification,
        is_enabled=event.is_enabled,
        data_quality_flags=event.data_quality_flags,
        created_by_user_id=event.created_by_user_id,
    )


async def _event_with_access(
    event_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> tuple[FinancialEvent, EventType]:
    result = await session.execute(
        select(FinancialEvent, EventType)
        .join(EventType, EventType.id == FinancialEvent.event_type_id)
        .join(
            HouseholdMembership,
            HouseholdMembership.household_id == FinancialEvent.household_id,
        )
        .where(
            FinancialEvent.id == event_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    event, event_type = row
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == event.household_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    assert membership is not None
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient household role")
    return event, event_type


async def _validate_event_references(
    household_id: uuid.UUID,
    payload: FinancialEventCreate,
    event_type: EventType,
    session: AsyncSession,
) -> None:
    if payload.property_id is not None:
        property_record = await session.get(Property, payload.property_id)
        if property_record is None or property_record.household_id != household_id:
            raise HTTPException(422, "Event property must belong to the household")
    if payload.person_id is not None:
        person = await session.get(Person, payload.person_id)
        if person is None or person.household_id != household_id:
            raise HTTPException(422, "Event person must belong to the household")
    if payload.loan_id is not None:
        loan = await session.get(Loan, payload.loan_id)
        if loan is None or loan.household_id != household_id:
            raise HTTPException(422, "Event loan must belong to the household")
    if event_type.code == "PROPERTY_STATUS_CHANGED":
        raw_status_id = payload.payload.get("status_id")
        try:
            status_id = uuid.UUID(str(raw_status_id))
        except TypeError, ValueError:
            raise HTTPException(422, "PROPERTY_STATUS_CHANGED requires a status_id") from None
        item = await session.get(LookupItem, status_id)
        if item is None or item.category != "property_status" or not item.is_active:
            raise HTTPException(422, "Active property_status lookup required")


@router.get("/event-types", response_model=list[EventTypeRead])
async def list_event_types(
    _: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[EventType]:
    return list(
        await session.scalars(
            select(EventType).where(EventType.is_active.is_(True)).order_by(EventType.priority)
        )
    )


@router.post(
    "/households/{household_id}/events", response_model=FinancialEventRead, status_code=201
)
async def create_event(
    household_id: uuid.UUID,
    payload: FinancialEventCreate,
    membership: Annotated[
        HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))
    ],
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialEventRead:
    if payload.idempotency_key is not None:
        duplicate = await session.scalar(
            select(FinancialEvent.id).where(
                FinancialEvent.household_id == household_id,
                FinancialEvent.idempotency_key == payload.idempotency_key,
            )
        )
        if duplicate is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Duplicate event idempotency key")
    event_type = await session.get(EventType, payload.event_type_id)
    if event_type is None or not event_type.is_active:
        raise HTTPException(422, "Active event type required")
    await _validate_event_references(household_id, payload, event_type, session)
    flags = event_quality_flags(
        event_type.code,
        payload.classification,
        payload.effective_at.date(),
        date.today(),
        payload.property_id is not None,
        payload.amount,
    )
    event = FinancialEvent(
        household_id=membership.household_id,
        created_by_user_id=user.id,
        data_quality_flags=flags,
        **payload.model_dump(),
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    logger.info("financial_event_created", event_id=str(event.id), event_type=event_type.code)
    return _event_read(event, event_type)


@router.patch("/events/{event_id}/enabled", response_model=FinancialEventRead)
async def toggle_event(
    event_id: uuid.UUID,
    payload: EventToggle,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialEventRead:
    event, event_type = await _event_with_access(event_id, HouseholdRole.EDITOR, user, session)
    if event.classification == EventClassification.OBSERVED:
        raise HTTPException(422, "Observed events cannot be toggled")
    event.is_enabled = payload.is_enabled
    await session.commit()
    await session.refresh(event)
    logger.info("financial_event_toggled", event_id=str(event.id), enabled=event.is_enabled)
    return _event_read(event, event_type)


@router.patch("/events/{event_id}", response_model=FinancialEventRead)
async def update_planned_event(
    event_id: uuid.UUID,
    payload: PlannedEventUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FinancialEventRead:
    event, event_type = await _event_with_access(event_id, HouseholdRole.EDITOR, user, session)
    if event.classification == EventClassification.OBSERVED:
        raise HTTPException(422, "Observed events cannot be edited")
    event.effective_at = payload.effective_at
    event.notes = payload.notes
    event.data_quality_flags = event_quality_flags(
        event_type.code,
        event.classification,
        payload.effective_at.date(),
        date.today(),
        event.property_id is not None,
        event.amount,
    )
    await session.commit()
    await session.refresh(event)
    logger.info("financial_event_updated", event_id=str(event.id))
    return _event_read(event, event_type)


@router.get("/households/{household_id}/timeline", response_model=TimelineRead)
async def household_timeline(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    include_disabled: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> TimelineRead:
    query = (
        select(FinancialEvent, EventType)
        .join(EventType, EventType.id == FinancialEvent.event_type_id)
        .where(FinancialEvent.household_id == household_id)
    )
    if not include_disabled:
        query = query.where(FinancialEvent.is_enabled.is_(True))
    if from_date is not None:
        query = query.where(
            FinancialEvent.effective_at >= datetime.combine(from_date, time.min, UTC)
        )
    if to_date is not None:
        query = query.where(
            FinancialEvent.effective_at
            < datetime.combine(to_date + timedelta(days=1), time.min, UTC)
        )
    rows = (
        await session.execute(
            query.order_by(
                FinancialEvent.effective_at,
                EventType.priority,
                FinancialEvent.recorded_at,
                FinancialEvent.id,
            )
        )
    ).all()
    events = [_event_read(event, event_type) for event, event_type in rows]
    flags = sorted({flag for event in events for flag in event.data_quality_flags})
    return TimelineRead(household_id=household_id, events=events, data_quality_flags=flags)


@router.get("/properties/{property_id}/state", response_model=ResolvedPropertyState)
async def resolve_property_state(
    property_id: uuid.UUID,
    as_of: date,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ResolvedPropertyState:
    property_record = await session.scalar(
        select(Property)
        .join(HouseholdMembership, HouseholdMembership.household_id == Property.household_id)
        .where(
            Property.id == property_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    if property_record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property not found")
    baseline = await session.scalar(
        select(PropertyBaseline)
        .where(
            PropertyBaseline.property_id == property_id,
            PropertyBaseline.baseline_date <= as_of,
        )
        .order_by(PropertyBaseline.baseline_date.desc())
        .limit(1)
    )
    state: dict[str, object] = {
        "property_value": baseline.property_value if baseline else None,
        "loan_balance_total": baseline.loan_balance_total if baseline else None,
        "status_id": str(baseline.status_id if baseline else property_record.current_status_id),
        "is_active_asset": None,
    }
    quality_flags = [] if baseline else ["BASELINE_MISSING"]
    start = (
        datetime.combine(baseline.baseline_date, time.max, UTC) if baseline is not None else None
    )
    query = (
        select(FinancialEvent, EventType)
        .join(EventType, EventType.id == FinancialEvent.event_type_id)
        .where(
            FinancialEvent.household_id == property_record.household_id,
            FinancialEvent.property_id == property_id,
            FinancialEvent.is_enabled.is_(True),
            FinancialEvent.effective_at
            < datetime.combine(as_of + timedelta(days=1), time.min, UTC),
        )
    )
    if start is not None:
        query = query.where(FinancialEvent.effective_at > start)
    rows = (
        await session.execute(
            query.order_by(
                FinancialEvent.effective_at,
                EventType.priority,
                FinancialEvent.recorded_at,
                FinancialEvent.id,
            )
        )
    ).all()
    applied_ids: list[uuid.UUID] = []
    for event, event_type in rows:
        apply_property_event(event, event_type.code, state)
        applied_ids.append(event.id)
        quality_flags.extend(event.data_quality_flags)
    status_id = uuid.UUID(str(state["status_id"]))
    status_item = await session.get(LookupItem, status_id)
    is_active = state["is_active_asset"]
    if is_active is None and status_item is not None:
        is_active = status_item.is_active_asset
    return ResolvedPropertyState(
        property_id=property_id,
        as_of=as_of,
        temporal_position=temporal_position(as_of, date.today()),
        baseline_id=baseline.id if baseline else None,
        baseline_date=baseline.baseline_date if baseline else None,
        property_value=Decimal(str(state["property_value"])) if state["property_value"] else None,
        loan_balance_total=(
            Decimal(str(state["loan_balance_total"]))
            if state["loan_balance_total"] is not None
            else None
        ),
        status_id=status_id,
        is_active_asset=bool(is_active) if is_active is not None else None,
        applied_event_ids=applied_ids,
        data_quality_flags=sorted(set(quality_flags)),
    )
