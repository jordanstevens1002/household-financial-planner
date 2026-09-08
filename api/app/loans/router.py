"""Loan API routes."""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.core.logging import get_logger
from app.events.router import _event_read
from app.events.schemas import FinancialEventRead
from app.loans.calculations import generate_schedule, minimum_repayment, money, payments_per_year
from app.loans.schemas import (
    DebtReconciliationStatus,
    GoalCreate,
    GoalRead,
    LoanBorrowerReplace,
    LoanCloseCreate,
    LoanCreate,
    LoanDebtBalanceRead,
    LoanEventCreate,
    LoanGroupCreate,
    LoanGroupRead,
    LoanGroupRemovalCreate,
    LoanGroupUpdate,
    LoanRead,
    LoanRepaymentResponsibilityRead,
    LoanRepaymentResponsibilitySetCreate,
    LoanRepaymentResponsibilitySetRead,
    LoanScheduleRead,
    LoanUpdate,
    PropertyDebtReconciliationRead,
    RefinanceCreate,
    RefinanceRead,
    TargetCalculationRead,
    TargetCalculationRequest,
)
from app.loans.service import canonical_borrower_ids, create_loan_record, validate_borrowers
from app.models import (
    ApplicationUser,
    EventClassification,
    EventType,
    FinancialEvent,
    Goal,
    HouseholdMembership,
    HouseholdRole,
    Loan,
    LoanBorrower,
    LoanGroup,
    LoanRepaymentResponsibility,
    LookupItem,
    Person,
    Property,
    PropertyBaseline,
)

router = APIRouter(prefix="/api/v1", tags=["loans"])
logger = get_logger(component="loans")
MAX_RECONCILIATION_YEARS = 100

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


@router.post("/loans/{loan_id}/close", response_model=LoanRead)
async def close_loan(
    loan_id: uuid.UUID,
    payload: LoanCloseCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Loan:
    accessible_loan = await _loan_with_access(loan_id, HouseholdRole.EDITOR, user, session)
    loan = await session.scalar(select(Loan).where(Loan.id == accessible_loan.id).with_for_update())
    assert loan is not None
    if not loan.is_active:
        raise HTTPException(409, "Loan is already closed")
    event_type = await session.scalar(
        select(EventType).where(
            EventType.code == "LOAN_CLOSED",
            EventType.is_active.is_(True),
        )
    )
    if event_type is None:
        raise HTTPException(422, "Active LOAN_CLOSED event type required")
    event = FinancialEvent(
        household_id=loan.household_id,
        loan_id=loan.id,
        event_type_id=event_type.id,
        effective_at=datetime.combine(payload.effective_date, time.min, UTC),
        payload={},
        notes=payload.notes,
        classification=EventClassification.OBSERVED,
        is_enabled=True,
        data_quality_flags=[],
        created_by_user_id=user.id,
    )
    before = _loan_snapshot(loan)
    loan.is_active = False
    session.add(event)
    await session.commit()
    await session.refresh(loan)
    logger.info(
        "loan_closed",
        actor_user_id=str(user.id),
        household_id=str(loan.household_id),
        property_id=str(loan.property_id) if loan.property_id else None,
        loan_id=str(loan.id),
        closure_event_id=str(event.id),
        effective_date=payload.effective_date.isoformat(),
        before=before,
        after=_loan_snapshot(loan),
    )
    return loan


@router.get("/households/{household_id}/loans", response_model=list[LoanRead])
async def list_loans(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Loan]:
    return list(await session.scalars(select(Loan).where(Loan.household_id == household_id)))


@router.get(
    "/properties/{property_id}/loan-debt-reconciliation",
    response_model=PropertyDebtReconciliationRead,
)
async def property_loan_debt_reconciliation(
    property_id: uuid.UUID,
    as_of: date,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyDebtReconciliationRead:
    latest_supported_date = date(date.today().year + MAX_RECONCILIATION_YEARS, 12, 31)
    if as_of > latest_supported_date:
        raise HTTPException(
            422,
            f"as_of cannot be more than {MAX_RECONCILIATION_YEARS} years in the future",
        )
    property_record = await session.scalar(
        select(Property)
        .join(HouseholdMembership, HouseholdMembership.household_id == Property.household_id)
        .where(
            Property.id == property_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    if property_record is None:
        raise HTTPException(404, "Property not found")
    baseline = await session.scalar(
        select(PropertyBaseline)
        .where(
            PropertyBaseline.property_id == property_id,
            PropertyBaseline.baseline_date <= as_of,
        )
        .order_by(PropertyBaseline.baseline_date.desc())
        .limit(1)
    )
    loans = list(
        await session.scalars(
            select(Loan).where(
                Loan.property_id == property_id,
                Loan.opening_balance_date <= as_of,
            )
        )
    )
    balances: list[LoanDebtBalanceRead] = []
    unprojectable_names: list[str] = []
    for loan in loans:
        try:
            schedule = generate_schedule(
                loan,
                await _loan_events(loan.id, session),
                as_of,
                include_entries=False,
            )
        except ValueError:
            unprojectable_names.append(loan.display_name)
            balances.append(
                LoanDebtBalanceRead(
                    loan_id=loan.id,
                    display_name=loan.display_name,
                    currency=loan.currency,
                    effective_balance=None,
                    data_quality_flags=["LOAN_BALANCE_CANNOT_BE_PROJECTED"],
                )
            )
            continue
        if schedule.remaining_balance > 0:
            balances.append(
                LoanDebtBalanceRead(
                    loan_id=loan.id,
                    display_name=loan.display_name,
                    currency=loan.currency,
                    effective_balance=schedule.remaining_balance,
                )
            )
    recorded = baseline.loan_balance_total if baseline is not None else None
    currencies = {item.currency for item in balances if item.effective_balance is not None}
    warnings: list[str] = []
    linked_total: Decimal | None
    difference: Decimal | None
    if unprojectable_names:
        status_value = DebtReconciliationStatus.UNPROJECTABLE_LOANS
        linked_total = None
        difference = None
        warnings.append(
            "Effective balances cannot be projected for: " + ", ".join(unprojectable_names)
        )
    elif currencies - {property_record.default_currency}:
        status_value = DebtReconciliationStatus.CURRENCY_MISMATCH
        linked_total = None
        difference = None
        warnings.append(
            "Linked loans use a currency other than the property's currency and cannot be totalled."
        )
    else:
        linked_total = money(
            sum(
                (item.effective_balance for item in balances if item.effective_balance is not None),
                Decimal("0"),
            )
        )
        difference = linked_total - recorded if recorded is not None else None
        if not balances:
            status_value = DebtReconciliationStatus.NO_LINKED_LOANS
            warnings.append("No linked loans were effective on this date.")
        elif recorded is None:
            status_value = DebtReconciliationStatus.RECORDED_DEBT_MISSING
            warnings.append("No property-debt observation was recorded on or before this date.")
        elif difference == 0:
            status_value = DebtReconciliationStatus.MATCHED
        else:
            status_value = DebtReconciliationStatus.MISMATCH
            warnings.append(
                "Recorded property debt differs from the effective linked-loan balance."
            )
    return PropertyDebtReconciliationRead(
        property_id=property_id,
        as_of=as_of,
        currency=property_record.default_currency,
        baseline_id=baseline.id if baseline is not None else None,
        recorded_debt_date=baseline.baseline_date if baseline is not None else None,
        recorded_property_debt=recorded,
        linked_loan_balance=linked_total,
        difference=difference,
        status=status_value,
        loans=balances,
        warnings=warnings,
    )


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
    duplicate = await session.scalar(
        select(LoanGroup.id).where(
            LoanGroup.household_id == household_id,
            LoanGroup.property_id == payload.property_id,
            func.lower(LoanGroup.display_name) == payload.display_name.lower(),
        )
    )
    if duplicate is not None:
        raise HTTPException(409, "A loan group with this name already exists for the property")
    group = LoanGroup(household_id=household_id, **payload.model_dump())
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def _loan_group_with_access(
    group_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> LoanGroup:
    group = await session.scalar(
        select(LoanGroup)
        .join(HouseholdMembership, HouseholdMembership.household_id == LoanGroup.household_id)
        .where(
            LoanGroup.id == group_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    if group is None:
        raise HTTPException(404, "Loan group not found")
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == group.household_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    assert membership is not None
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(403, "Insufficient household role")
    return group


@router.patch("/loan-groups/{group_id}", response_model=LoanGroupRead)
async def update_loan_group(
    group_id: uuid.UUID,
    payload: LoanGroupUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanGroup:
    accessible = await _loan_group_with_access(group_id, HouseholdRole.EDITOR, user, session)
    group = await session.scalar(
        select(LoanGroup).where(LoanGroup.id == accessible.id).with_for_update()
    )
    assert group is not None
    duplicate = await session.scalar(
        select(LoanGroup.id).where(
            LoanGroup.household_id == group.household_id,
            LoanGroup.property_id == group.property_id,
            func.lower(LoanGroup.display_name) == payload.display_name.lower(),
            LoanGroup.id != group.id,
        )
    )
    if duplicate is not None:
        raise HTTPException(409, "A loan group with this name already exists for the property")
    previous_name = group.display_name
    group.display_name = payload.display_name
    await session.commit()
    await session.refresh(group)
    logger.info(
        "loan_group_renamed",
        actor_user_id=str(user.id),
        household_id=str(group.household_id),
        property_id=str(group.property_id) if group.property_id else None,
        loan_group_id=str(group.id),
        previous_name=previous_name,
        resulting_name=group.display_name,
    )
    return group


@router.delete("/loan-groups/{group_id}", status_code=204)
async def delete_loan_group(
    group_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    accessible = await _loan_group_with_access(group_id, HouseholdRole.EDITOR, user, session)
    group = await session.scalar(
        select(LoanGroup).where(LoanGroup.id == accessible.id).with_for_update()
    )
    assert group is not None
    assigned_loans = list(
        await session.scalars(
            select(Loan)
            .where(Loan.loan_group_id == group.id)
            .order_by(Loan.display_name, Loan.id)
            .with_for_update()
        )
    )
    if assigned_loans:
        raise HTTPException(409, "Use the populated-group removal action after reviewing its loans")
    await _remove_locked_loan_group(group, assigned_loans, user, session)


@router.post("/loan-groups/{group_id}/remove", status_code=204)
async def remove_populated_loan_group(
    group_id: uuid.UUID,
    payload: LoanGroupRemovalCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    accessible = await _loan_group_with_access(group_id, HouseholdRole.ADMIN, user, session)
    group = await session.scalar(
        select(LoanGroup).where(LoanGroup.id == accessible.id).with_for_update()
    )
    assert group is not None
    assigned_loans = list(
        await session.scalars(
            select(Loan)
            .where(Loan.loan_group_id == group.id)
            .order_by(Loan.display_name, Loan.id)
            .with_for_update()
        )
    )
    if set(payload.assigned_loan_ids) != {loan.id for loan in assigned_loans}:
        raise HTTPException(
            409,
            "Loan assignments changed; review the affected loans and confirm again",
        )
    await _remove_locked_loan_group(group, assigned_loans, user, session)


async def _remove_locked_loan_group(
    group: LoanGroup,
    assigned_loans: list[Loan],
    user: ApplicationUser,
    session: AsyncSession,
) -> None:
    snapshot = LoanGroupRead.model_validate(group).model_dump(mode="json")
    affected_loans = [
        {"id": str(loan.id), "display_name": loan.display_name} for loan in assigned_loans
    ]
    for loan in assigned_loans:
        loan.loan_group_id = None
    await session.delete(group)
    await session.commit()
    logger.info(
        "loan_group_removed",
        actor_user_id=str(user.id),
        household_id=str(group.household_id),
        property_id=str(group.property_id) if group.property_id else None,
        loan_group_id=str(group.id),
        removed_group=snapshot,
        affected_loans=affected_loans,
    )


@router.get("/households/{household_id}/loan-groups", response_model=list[LoanGroupRead])
async def list_loan_groups(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[LoanGroup]:
    return list(
        await session.scalars(
            select(LoanGroup)
            .where(LoanGroup.household_id == household_id)
            .order_by(LoanGroup.display_name, LoanGroup.id)
        )
    )


@router.post("/households/{household_id}/loans", response_model=LoanRead, status_code=201)
async def create_loan(
    household_id: uuid.UUID,
    payload: LoanCreate,
    actor: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Loan:
    loan = await create_loan_record(household_id, payload, session)
    await session.commit()
    await session.refresh(loan)
    logger.info(
        "loan_created",
        actor_user_id=str(actor.application_user_id),
        household_id=str(household_id),
        property_id=str(loan.property_id) if loan.property_id else None,
        loan_id=str(loan.id),
        borrower_person_ids=[str(person_id) for person_id in loan.borrower_person_ids],
    )
    return loan


def _loan_snapshot(loan: Loan) -> dict[str, object]:
    return LoanRead.model_validate(loan).model_dump(mode="json")


@router.patch("/loans/{loan_id}", response_model=LoanRead)
async def update_loan(
    loan_id: uuid.UUID,
    payload: LoanUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Loan:
    accessible_loan = await _loan_with_access(loan_id, HouseholdRole.EDITOR, user, session)
    loan = await session.scalar(select(Loan).where(Loan.id == accessible_loan.id).with_for_update())
    assert loan is not None
    values = payload.model_dump(exclude_unset=True)
    if "loan_type_id" in values and values["loan_type_id"] != loan.loan_type_id:
        loan_type = await session.get(LookupItem, values["loan_type_id"])
        if loan_type is None or loan_type.category != "loan_type" or not loan_type.is_active:
            raise HTTPException(422, "Active loan_type lookup required")
    if "loan_group_id" in values and values["loan_group_id"] is not None:
        group = await session.get(LoanGroup, values["loan_group_id"])
        if (
            group is None
            or group.household_id != loan.household_id
            or group.property_id != loan.property_id
        ):
            raise HTTPException(422, "Loan group must belong to the same property and household")
    before = _loan_snapshot(loan)
    for field, value in values.items():
        setattr(loan, field, value)
    await session.commit()
    await session.refresh(loan)
    logger.info(
        "loan_corrected",
        actor_user_id=str(user.id),
        household_id=str(loan.household_id),
        property_id=str(loan.property_id) if loan.property_id else None,
        loan_id=str(loan.id),
        changed_fields=sorted(values),
        before=before,
        after=_loan_snapshot(loan),
    )
    return loan


@router.get("/loans/{loan_id}", response_model=LoanRead)
async def get_loan(
    loan_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Loan:
    return await _loan_with_access(loan_id, HouseholdRole.VIEWER, user, session)


@router.put("/loans/{loan_id}/borrowers", response_model=LoanRead)
async def replace_loan_borrowers(
    loan_id: uuid.UUID,
    payload: LoanBorrowerReplace,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Loan:
    accessible = await _loan_with_access(loan_id, HouseholdRole.EDITOR, user, session)
    loan = await session.scalar(select(Loan).where(Loan.id == accessible.id).with_for_update())
    assert loan is not None
    requested_ids = canonical_borrower_ids(payload.borrower_person_ids)
    await validate_borrowers(loan.household_id, requested_ids, session)
    previous_ids = canonical_borrower_ids(loan.borrower_person_ids)
    existing_by_person_id = {link.person_id: link for link in loan.borrower_links}
    loan.borrower_links = [
        existing_by_person_id.get(person_id, LoanBorrower(person_id=person_id))
        for person_id in requested_ids
    ]
    await session.commit()
    logger.info(
        "loan_borrowers_replaced",
        actor_user_id=str(user.id),
        household_id=str(loan.household_id),
        property_id=str(loan.property_id) if loan.property_id else None,
        loan_id=str(loan.id),
        previous_borrower_person_ids=[str(person_id) for person_id in previous_ids],
        resulting_borrower_person_ids=[str(person_id) for person_id in requested_ids],
    )
    return loan


@router.get(
    "/loans/{loan_id}/repayment-responsibilities",
    response_model=list[LoanRepaymentResponsibilityRead],
)
async def list_repayment_responsibilities(
    loan_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LoanRepaymentResponsibility]:
    await _loan_with_access(loan_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(LoanRepaymentResponsibility)
            .where(LoanRepaymentResponsibility.loan_id == loan_id)
            .order_by(
                LoanRepaymentResponsibility.effective_from,
                LoanRepaymentResponsibility.id,
            )
        )
    )


@router.put(
    "/loans/{loan_id}/repayment-responsibilities/{effective_from}",
    response_model=LoanRepaymentResponsibilitySetRead,
)
async def replace_repayment_responsibility_set(
    loan_id: uuid.UUID,
    effective_from: date,
    payload: LoanRepaymentResponsibilitySetCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> LoanRepaymentResponsibilitySetRead:
    accessible = await _loan_with_access(loan_id, HouseholdRole.EDITOR, user, session)
    loan = await session.scalar(select(Loan).where(Loan.id == accessible.id).with_for_update())
    assert loan is not None
    if payload.effective_to is not None and payload.effective_to < effective_from:
        raise HTTPException(422, "effective_to must not precede effective_from")
    people = list(
        await session.scalars(
            select(Person).where(
                Person.id.in_([allocation.person_id for allocation in payload.allocations])
            )
        )
    )
    people_by_id = {person.id: person for person in people}
    for allocation in payload.allocations:
        person = people_by_id.get(allocation.person_id)
        if person is None or person.household_id != loan.household_id:
            raise HTTPException(422, "Responsible person must belong to the loan household")
        if (
            not person.is_active
            or person.effective_from > effective_from
            or (
                person.effective_to is not None
                and (payload.effective_to is None or person.effective_to < payload.effective_to)
            )
        ):
            raise HTTPException(
                422,
                "Responsible people must be active for the complete allocation interval",
            )
    previous = list(
        await session.scalars(
            select(LoanRepaymentResponsibility).where(
                LoanRepaymentResponsibility.loan_id == loan.id,
                LoanRepaymentResponsibility.effective_from == effective_from,
            )
        )
    )
    await session.execute(
        delete(LoanRepaymentResponsibility).where(
            LoanRepaymentResponsibility.loan_id == loan.id,
            LoanRepaymentResponsibility.effective_from == effective_from,
        )
    )
    records = [
        LoanRepaymentResponsibility(
            loan_id=loan.id,
            person_id=allocation.person_id,
            responsibility_percentage=allocation.responsibility_percentage,
            effective_from=effective_from,
            effective_to=payload.effective_to,
            notes=allocation.notes,
        )
        for allocation in payload.allocations
    ]
    session.add_all(records)
    await session.flush()
    await session.commit()
    logger.info(
        "loan_repayment_responsibility_set_replaced",
        actor_user_id=str(user.id),
        household_id=str(loan.household_id),
        property_id=str(loan.property_id) if loan.property_id else None,
        loan_id=str(loan.id),
        effective_from=effective_from.isoformat(),
        effective_to=payload.effective_to.isoformat() if payload.effective_to else None,
        previous_responsibility_ids=[str(item.id) for item in previous],
        resulting_responsibility_ids=[str(item.id) for item in records],
        allocations=[
            {
                "person_id": str(record.person_id),
                "responsibility_percentage": f"{record.responsibility_percentage:.2f}",
            }
            for record in records
        ],
    )
    return LoanRepaymentResponsibilitySetRead(
        effective_from=effective_from,
        effective_to=payload.effective_to,
        responsibilities=[
            LoanRepaymentResponsibilityRead.model_validate(record) for record in records
        ],
        total_percentage=Decimal("100"),
        warnings=[],
    )


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
    replacement = await create_loan_record(old_loan.household_id, payload.replacement_loan, session)
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
