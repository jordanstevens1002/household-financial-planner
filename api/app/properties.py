import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
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
    Property,
    PropertyBaseline,
    PropertyOwnershipInterest,
    PropertyValuation,
    ValuationType,
)
from app.schemas import (
    BaselineCreate,
    BaselineRead,
    OwnershipCreate,
    OwnershipRead,
    OwnershipResult,
    PropertyCreate,
    PropertyRead,
    PropertySetupMode,
    PropertyWizardCreate,
    PropertyWizardRead,
    ValuationCreate,
    ValuationRead,
)

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


@router.get("/households/{household_id}/properties", response_model=list[PropertyRead])
async def list_properties(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Property]:
    return list(
        await session.scalars(select(Property).where(Property.household_id == household_id))
    )


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
    record = PropertyOwnershipInterest(property_id=property_id, **payload.model_dump())
    session.add(record)
    await session.flush()
    total = await _ownership_total(property_id, payload.effective_from, session)
    await session.commit()
    await session.refresh(record)
    return OwnershipResult(
        ownership=OwnershipRead.model_validate(record),
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
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> PropertyWizardRead:
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
    session.add_all(ownership_records)
    await session.flush()
    total = sum((item.ownership_percentage for item in payload.ownership), Decimal("0"))
    warnings = _ownership_warnings(total)
    await session.commit()
    logger.info("property_setup_completed", property_id=str(property_record.id), mode=payload.mode)
    return PropertyWizardRead(
        property=PropertyRead.model_validate(property_record),
        valuation=ValuationRead.model_validate(valuation) if valuation else None,
        baseline=BaselineRead.model_validate(baseline) if baseline else None,
        ownership=[OwnershipRead.model_validate(item) for item in ownership_records],
        warnings=warnings,
    )
