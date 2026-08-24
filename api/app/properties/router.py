"""Property and ownership API routes."""

import uuid
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.core.logging import get_logger
from app.loans.schemas import LoanRead
from app.loans.service import create_loan_record
from app.models import (
    ApplicationUser,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    OwnerType,
    Person,
    Property,
    PropertyBaseline,
    PropertyOwnershipInterest,
    PropertyValuation,
    ValuationType,
)
from app.properties.schemas import (
    BaselineCreate,
    BaselineRead,
    OwnershipCorrection,
    OwnershipCreate,
    OwnershipPosition,
    OwnershipRead,
    OwnershipResult,
    PropertyCreate,
    PropertyRead,
    PropertySetupMode,
    PropertySummaryRead,
    PropertyWizardCreate,
    PropertyWizardRead,
    ValuationCreate,
    ValuationRead,
)
from app.properties.valuations import valuation_priority_expression

router = APIRouter(prefix="/api/v1", tags=["properties"])
logger = get_logger(component="properties")


async def _property_with_access(
    property_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> Property:
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
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == property_record.household_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    assert membership is not None
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient household role")
    return property_record


async def _validate_lookup(
    lookup_id: uuid.UUID, category: str, session: AsyncSession
) -> LookupItem:
    item = await session.get(LookupItem, lookup_id)
    if item is None or item.category != category or not item.is_active:
        raise HTTPException(422, f"Active {category} lookup required")
    return item


async def _ownership_total(
    property_id: uuid.UUID, effective_date: date, session: AsyncSession
) -> Decimal:
    total = await session.scalar(
        select(func.coalesce(func.sum(PropertyOwnershipInterest.ownership_percentage), 0)).where(
            PropertyOwnershipInterest.property_id == property_id,
            PropertyOwnershipInterest.effective_from <= effective_date,
            or_(
                PropertyOwnershipInterest.effective_to.is_(None),
                PropertyOwnershipInterest.effective_to >= effective_date,
            ),
        )
    )
    return Decimal(total or 0)


def _ownership_warnings(total: Decimal) -> list[str]:
    if total == Decimal("100"):
        return []
    return [f"Ownership totals {total:.2f}% rather than 100.00% for the effective date"]


@dataclass(frozen=True)
class _OwnershipCandidate:
    id: uuid.UUID | None
    owner_type: OwnerType
    person_id: uuid.UUID | None
    external_owner_name: str | None
    ownership_percentage: Decimal
    effective_from: date
    effective_to: date | None


def _ownership_candidate(
    record: PropertyOwnershipInterest | OwnershipCreate,
) -> _OwnershipCandidate:
    return _OwnershipCandidate(
        id=record.id if isinstance(record, PropertyOwnershipInterest) else None,
        owner_type=record.owner_type,
        person_id=record.person_id,
        external_owner_name=record.external_owner_name,
        ownership_percentage=record.ownership_percentage,
        effective_from=record.effective_from,
        effective_to=record.effective_to,
    )


def _owner_key(record: _OwnershipCandidate) -> tuple[OwnerType, str]:
    if record.owner_type == OwnerType.PERSON:
        return record.owner_type, str(record.person_id)
    if record.owner_type == OwnerType.HOUSEHOLD:
        return record.owner_type, "household"
    return record.owner_type, (record.external_owner_name or "").strip().casefold()


def _intervals_overlap(left: _OwnershipCandidate, right: _OwnershipCandidate) -> bool:
    return (left.effective_to is None or left.effective_to >= right.effective_from) and (
        right.effective_to is None or right.effective_to >= left.effective_from
    )


def _validate_ownership_timeline(records: list[_OwnershipCandidate]) -> None:
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            if _owner_key(left) == _owner_key(right) and _intervals_overlap(left, right):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "This owner already has an ownership record for the selected dates. "
                    "Correct or close the existing record before adding another.",
                )
    boundaries = {record.effective_from for record in records}
    boundaries.update(
        date.fromordinal(record.effective_to.toordinal() + 1)
        for record in records
        if record.effective_to is not None and record.effective_to != date.max
    )
    for boundary in boundaries:
        total = sum(
            (
                record.ownership_percentage
                for record in records
                if record.effective_from <= boundary
                and (record.effective_to is None or record.effective_to >= boundary)
            ),
            Decimal("0"),
        )
        if total > Decimal("100"):
            raise HTTPException(
                422,
                f"Ownership cannot exceed 100% (total {total:.2f}% from {boundary.isoformat()})",
            )


async def _validate_ownership_write(
    property_id: uuid.UUID,
    additions: list[_OwnershipCandidate],
    session: AsyncSession,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    await session.execute(select(Property.id).where(Property.id == property_id).with_for_update())
    existing_query = select(PropertyOwnershipInterest).where(
        PropertyOwnershipInterest.property_id == property_id
    )
    if exclude_id is not None:
        existing_query = existing_query.where(PropertyOwnershipInterest.id != exclude_id)
    existing = list(await session.scalars(existing_query))
    _validate_ownership_timeline([_ownership_candidate(record) for record in existing] + additions)


async def _create_property(
    household_id: uuid.UUID, payload: PropertyCreate, session: AsyncSession
) -> Property:
    await _validate_lookup(payload.property_type_id, "property_type", session)
    await _validate_lookup(payload.current_status_id, "property_status", session)
    household = await session.get(Household, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    values = payload.model_dump()
    values["default_currency"] = payload.default_currency or household.currency
    record = Property(household_id=household_id, **values)
    session.add(record)
    await session.flush()
    return record


async def _validate_setup_loans(
    household_id: uuid.UUID,
    payload: PropertyWizardCreate,
    session: AsyncSession,
) -> None:
    if not payload.loans:
        return
    household = await session.get(Household, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
    property_currency = payload.property.default_currency or household.currency
    for loan in payload.loans:
        if loan.currency is not None and loan.currency != property_currency:
            raise HTTPException(422, "Setup loan currency must match the property currency")
        await _validate_lookup(loan.loan_type_id, "loan_type", session)


@router.get("/households/{household_id}/properties", response_model=list[PropertyRead])
async def list_properties(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Property]:
    return list(
        await session.scalars(select(Property).where(Property.household_id == household_id))
    )


@router.get(
    "/households/{household_id}/property-summaries",
    response_model=list[PropertySummaryRead],
)
async def list_property_summaries(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[PropertySummaryRead]:
    properties = list(
        await session.scalars(
            select(Property)
            .where(Property.household_id == household_id)
            .order_by(Property.display_name, Property.id)
        )
    )
    summaries: list[PropertySummaryRead] = []
    for property_record in properties:
        baseline = await session.scalar(
            select(PropertyBaseline)
            .where(PropertyBaseline.property_id == property_record.id)
            .order_by(PropertyBaseline.baseline_date.desc(), PropertyBaseline.id.desc())
            .limit(1)
        )
        valuation = await session.scalar(
            select(PropertyValuation)
            .where(
                PropertyValuation.property_id == property_record.id,
                PropertyValuation.valuation_type != ValuationType.SCENARIO_VALUE,
            )
            .order_by(
                PropertyValuation.valuation_date.desc(),
                valuation_priority_expression().desc(),
                PropertyValuation.id.desc(),
            )
            .limit(1)
        )
        valuation_is_latest = valuation is not None and (
            baseline is None or valuation.valuation_date > baseline.baseline_date
        )
        if baseline is not None:
            setup_mode = PropertySetupMode.CURRENT_SNAPSHOT
        elif property_record.purchase_date is not None:
            setup_mode = PropertySetupMode.HISTORICAL_PURCHASE
        else:
            setup_mode = None
        summaries.append(
            PropertySummaryRead(
                id=property_record.id,
                display_name=property_record.display_name,
                property_type_id=property_record.property_type_id,
                current_status_id=(
                    baseline.status_id if baseline else property_record.current_status_id
                ),
                currency=property_record.default_currency,
                purchase_date=property_record.purchase_date,
                purchase_price=property_record.purchase_price,
                setup_mode=setup_mode,
                position_date=(
                    valuation.valuation_date
                    if valuation_is_latest and valuation is not None
                    else baseline.baseline_date
                    if baseline
                    else None
                ),
                current_value=(
                    valuation.value
                    if valuation_is_latest and valuation is not None
                    else baseline.property_value
                    if baseline
                    else None
                ),
                total_property_debt=baseline.loan_balance_total if baseline else None,
            )
        )
    return summaries


@router.post("/households/{household_id}/properties", response_model=PropertyRead, status_code=201)
async def create_property(
    household_id: uuid.UUID,
    payload: PropertyCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Property:
    record = await _create_property(household_id, payload, session)
    await session.commit()
    await session.refresh(record)
    return record


@router.get("/properties/{property_id}", response_model=PropertyRead)
async def get_property(
    property_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Property:
    return await _property_with_access(property_id, HouseholdRole.VIEWER, user, session)


@router.post("/properties/{property_id}/valuations", response_model=ValuationRead, status_code=201)
async def create_valuation(
    property_id: uuid.UUID,
    payload: ValuationCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyValuation:
    await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    record = PropertyValuation(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.post("/properties/{property_id}/ownership", response_model=OwnershipResult, status_code=201)
async def create_ownership(
    property_id: uuid.UUID,
    payload: OwnershipCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OwnershipResult:
    property_record = await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    if payload.owner_type == OwnerType.PERSON:
        person = await session.get(Person, payload.person_id)
        if person is None or person.household_id != property_record.household_id:
            raise HTTPException(422, "Owner person must belong to the property household")
    await _validate_ownership_write(property_id, [_ownership_candidate(payload)], session)
    record = PropertyOwnershipInterest(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.flush()
    total = await _ownership_total(property_id, payload.effective_from, session)
    await session.commit()
    await session.refresh(record)
    logger.info(
        "property_ownership_created",
        actor_user_id=str(user.id),
        household_id=str(property_record.household_id),
        property_id=str(property_id),
        ownership_id=str(record.id),
        owner_type=record.owner_type,
        person_id=str(record.person_id) if record.person_id else None,
        external_owner_name=record.external_owner_name,
        ownership_percentage=str(record.ownership_percentage),
        effective_from=record.effective_from.isoformat(),
        effective_to=record.effective_to.isoformat() if record.effective_to else None,
    )
    return OwnershipResult(
        ownership=OwnershipRead.model_validate(record),
        total_percentage=total,
        warnings=_ownership_warnings(total),
    )


@router.patch(
    "/properties/{property_id}/ownership/{ownership_id}",
    response_model=OwnershipResult,
)
async def correct_ownership(
    property_id: uuid.UUID,
    ownership_id: uuid.UUID,
    payload: OwnershipCorrection,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OwnershipResult:
    property_record = await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    record = await session.get(PropertyOwnershipInterest, ownership_id)
    if record is None or record.property_id != property_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ownership record not found")
    previous_percentage = record.ownership_percentage
    previous_effective_to = record.effective_to
    previous_notes = record.notes
    values = payload.model_dump(exclude_unset=True)
    candidate = replace(
        _ownership_candidate(record),
        ownership_percentage=values.get("ownership_percentage", record.ownership_percentage),
        effective_to=values.get("effective_to", record.effective_to),
    )
    if candidate.effective_to and candidate.effective_to < candidate.effective_from:
        raise HTTPException(422, "effective_to must not precede effective_from")
    await _validate_ownership_write(property_id, [candidate], session, exclude_id=ownership_id)
    for field, value in values.items():
        setattr(record, field, value)
    await session.commit()
    await session.refresh(record)
    total = await _ownership_total(property_id, record.effective_from, session)
    logger.info(
        "property_ownership_corrected",
        actor_user_id=str(user.id),
        household_id=str(property_record.household_id),
        property_id=str(property_id),
        ownership_id=str(record.id),
        owner_type=record.owner_type,
        person_id=str(record.person_id) if record.person_id else None,
        external_owner_name=record.external_owner_name,
        effective_from=record.effective_from.isoformat(),
        previous_percentage=str(previous_percentage),
        resulting_percentage=str(record.ownership_percentage),
        previous_effective_to=(
            previous_effective_to.isoformat() if previous_effective_to else None
        ),
        resulting_effective_to=(record.effective_to.isoformat() if record.effective_to else None),
        notes_changed=previous_notes != record.notes,
    )
    return OwnershipResult(
        ownership=OwnershipRead.model_validate(record),
        total_percentage=total,
        warnings=_ownership_warnings(total),
    )


@router.get("/properties/{property_id}/ownership", response_model=list[OwnershipRead])
async def list_ownership(
    property_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PropertyOwnershipInterest]:
    await _property_with_access(property_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(PropertyOwnershipInterest)
            .where(PropertyOwnershipInterest.property_id == property_id)
            .order_by(
                PropertyOwnershipInterest.effective_from,
                PropertyOwnershipInterest.id,
            )
        )
    )


@router.get(
    "/properties/{property_id}/ownership-position",
    response_model=OwnershipPosition,
)
async def resolve_ownership_position(
    property_id: uuid.UUID,
    as_of: date,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OwnershipPosition:
    await _property_with_access(property_id, HouseholdRole.VIEWER, user, session)
    records = list(
        await session.scalars(
            select(PropertyOwnershipInterest)
            .where(
                PropertyOwnershipInterest.property_id == property_id,
                PropertyOwnershipInterest.effective_from <= as_of,
                or_(
                    PropertyOwnershipInterest.effective_to.is_(None),
                    PropertyOwnershipInterest.effective_to >= as_of,
                ),
            )
            .order_by(
                PropertyOwnershipInterest.ownership_percentage.desc(),
                PropertyOwnershipInterest.id,
            )
        )
    )
    total = sum((record.ownership_percentage for record in records), Decimal("0")).quantize(
        Decimal("0.01")
    )
    return OwnershipPosition(
        as_of=as_of,
        ownership=[OwnershipRead.model_validate(record) for record in records],
        total_percentage=total,
        warnings=_ownership_warnings(total),
    )


@router.post("/properties/{property_id}/baselines", response_model=BaselineRead, status_code=201)
async def create_baseline(
    property_id: uuid.UUID,
    payload: BaselineCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyBaseline:
    await _property_with_access(property_id, HouseholdRole.EDITOR, user, session)
    await _validate_lookup(payload.status_id, "property_status", session)
    record = PropertyBaseline(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@router.post(
    "/households/{household_id}/properties/wizard",
    response_model=PropertyWizardRead,
    status_code=201,
)
async def property_wizard(
    household_id: uuid.UUID,
    payload: PropertyWizardCreate,
    actor: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> PropertyWizardRead:
    await _validate_setup_loans(household_id, payload, session)
    property_record = await _create_property(household_id, payload.property, session)
    valuation: PropertyValuation | None = None
    baseline: PropertyBaseline | None = None
    if payload.mode == PropertySetupMode.HISTORICAL_PURCHASE:
        valuation_payload = payload.valuation or ValuationCreate(
            valuation_date=payload.property.purchase_date,
            value=payload.property.purchase_price,
            valuation_type=ValuationType.PURCHASE_PRICE,
            is_estimate=False,
        )
        valuation = PropertyValuation(
            property_id=property_record.id, **valuation_payload.model_dump()
        )
        session.add(valuation)
    elif payload.baseline is not None:
        await _validate_lookup(payload.baseline.status_id, "property_status", session)
        baseline = PropertyBaseline(property_id=property_record.id, **payload.baseline.model_dump())
        session.add(baseline)
    loan_records = []
    for loan_payload in payload.loans:
        loan_records.append(
            await create_loan_record(
                household_id,
                loan_payload.model_copy(
                    update={
                        "currency": property_record.default_currency,
                        "property_id": property_record.id,
                    }
                ),
                session,
            )
        )
    ownership_records = [
        PropertyOwnershipInterest(property_id=property_record.id, **item.model_dump())
        for item in payload.ownership
    ]
    person_ids = [
        item.person_id for item in payload.ownership if item.owner_type == OwnerType.PERSON
    ]
    if person_ids:
        valid_person_count = await session.scalar(
            select(func.count(Person.id)).where(
                Person.id.in_(person_ids), Person.household_id == household_id
            )
        )
        if valid_person_count != len(set(person_ids)):
            raise HTTPException(422, "Owner person must belong to the property household")
    await _validate_ownership_write(
        property_record.id,
        [_ownership_candidate(item) for item in payload.ownership],
        session,
    )
    session.add_all(ownership_records)
    await session.flush()
    total = sum((item.ownership_percentage for item in payload.ownership), Decimal("0"))
    warnings = _ownership_warnings(total)
    if (
        payload.mode == PropertySetupMode.CURRENT_SNAPSHOT
        and payload.baseline is not None
        and payload.baseline.loan_balance_total > 0
        and not loan_records
    ):
        warnings.append(
            "Property debt was recorded without linked loans; add loan details to reconcile it."
        )
    await session.commit()
    logger.info(
        "property_setup_completed",
        property_id=str(property_record.id),
        mode=payload.mode,
        loan_count=len(loan_records),
    )
    for record in ownership_records:
        logger.info(
            "property_ownership_created",
            actor_user_id=str(actor.application_user_id),
            household_id=str(household_id),
            property_id=str(property_record.id),
            ownership_id=str(record.id),
            owner_type=record.owner_type,
            person_id=str(record.person_id) if record.person_id else None,
            external_owner_name=record.external_owner_name,
            ownership_percentage=str(record.ownership_percentage),
            effective_from=record.effective_from.isoformat(),
            effective_to=record.effective_to.isoformat() if record.effective_to else None,
        )
    return PropertyWizardRead(
        property=PropertyRead.model_validate(property_record),
        valuation=ValuationRead.model_validate(valuation) if valuation else None,
        baseline=BaselineRead.model_validate(baseline) if baseline else None,
        ownership=[OwnershipRead.model_validate(item) for item in ownership_records],
        loans=[LoanRead.model_validate(item) for item in loan_records],
        warnings=warnings,
    )
