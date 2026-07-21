import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.income import _annual_value
from app.logging import get_logger
from app.models import (
    ApplicationUser,
    AustralianSuperProfile,
    Household,
    HouseholdMembership,
    HouseholdRole,
    IncomeSource,
    LookupItem,
    Person,
    RetirementAccount,
    RetirementAccountEvent,
    RetirementContributionProfile,
)
from app.retirement_calculations import ContributionTerms, money, project_retirement
from app.retirement_schemas import (
    AustralianSuperProfileCreate,
    ContributionProfileCreate,
    ContributionProfileRead,
    RetirementAccountCreate,
    RetirementAccountRead,
    RetirementAccountUpdate,
    RetirementEventCreate,
    RetirementEventRead,
    RetirementProjectionRead,
)

router = APIRouter(prefix="/api/v1", tags=["retirement"])
logger = get_logger(component="retirement")


async def _account_with_access(
    account_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> RetirementAccount:
    row = (
        await session.execute(
            select(RetirementAccount, HouseholdMembership)
            .join(
                HouseholdMembership,
                HouseholdMembership.household_id == RetirementAccount.household_id,
            )
            .where(
                RetirementAccount.id == account_id,
                HouseholdMembership.application_user_id == user.id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Retirement account not found")
    account, membership = row
    assert isinstance(account, RetirementAccount)
    assert isinstance(membership, HouseholdMembership)
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(403, "Insufficient household role")
    return account


async def _account_read(account: RetirementAccount, session: AsyncSession) -> RetirementAccountRead:
    profile = await session.scalar(
        select(AustralianSuperProfile).where(
            AustralianSuperProfile.retirement_account_id == account.id
        )
    )
    data = RetirementAccountRead.model_validate(account).model_dump()
    if profile is not None:
        data["australian_super"] = AustralianSuperProfileCreate.model_validate(
            profile, from_attributes=True
        )
    return RetirementAccountRead.model_validate(data)


@router.get(
    "/households/{household_id}/retirement-accounts",
    response_model=list[RetirementAccountRead],
)
async def list_retirement_accounts(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[RetirementAccountRead]:
    accounts = list(
        await session.scalars(
            select(RetirementAccount).where(RetirementAccount.household_id == household_id)
        )
    )
    return [await _account_read(account, session) for account in accounts]


@router.post(
    "/households/{household_id}/retirement-accounts",
    response_model=RetirementAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_retirement_account(
    household_id: uuid.UUID,
    payload: RetirementAccountCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> RetirementAccountRead:
    household = await session.get(Household, household_id)
    assert household is not None
    account_type = await session.get(LookupItem, payload.account_type_id)
    if (
        account_type is None
        or account_type.category != "retirement_account_type"
        or not account_type.is_active
    ):
        raise HTTPException(422, "Active retirement_account_type lookup required")
    if payload.person_id is not None:
        person = await session.get(Person, payload.person_id)
        if person is None or person.household_id != household_id:
            raise HTTPException(422, "Account person must belong to the household")
    if account_type.code == "AUSTRALIAN_SUP" and payload.australian_super is None:
        raise HTTPException(422, "Australian super accounts require an australian_super profile")
    if account_type.code != "AUSTRALIAN_SUP" and payload.australian_super is not None:
        raise HTTPException(422, "australian_super is only valid for AUSTRALIAN_SUP accounts")
    values = payload.model_dump(exclude={"australian_super"})
    values["currency"] = payload.currency or household.currency
    account = RetirementAccount(household_id=household_id, **values)
    session.add(account)
    await session.flush()
    if payload.australian_super is not None:
        session.add(
            AustralianSuperProfile(
                retirement_account_id=account.id, **payload.australian_super.model_dump()
            )
        )
    await session.commit()
    await session.refresh(account)
    logger.info("retirement_account_created", account_id=str(account.id))
    return await _account_read(account, session)


@router.put("/retirement-accounts/{account_id}", response_model=RetirementAccountRead)
async def update_retirement_account(
    account_id: uuid.UUID,
    payload: RetirementAccountUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RetirementAccountRead:
    account = await _account_with_access(account_id, HouseholdRole.EDITOR, user, session)
    for name, value in payload.model_dump().items():
        setattr(account, name, value)
    await session.commit()
    await session.refresh(account)
    return await _account_read(account, session)


@router.get(
    "/retirement-accounts/{account_id}/contribution-profiles",
    response_model=list[ContributionProfileRead],
)
async def list_contribution_profiles(
    account_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RetirementContributionProfile]:
    await _account_with_access(account_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(RetirementContributionProfile)
            .where(RetirementContributionProfile.retirement_account_id == account_id)
            .order_by(RetirementContributionProfile.effective_from)
        )
    )


@router.post(
    "/retirement-accounts/{account_id}/contribution-profiles",
    response_model=ContributionProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_contribution_profile(
    account_id: uuid.UUID,
    payload: ContributionProfileCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RetirementContributionProfile:
    await _account_with_access(account_id, HouseholdRole.EDITOR, user, session)
    overlap_conditions = [
        RetirementContributionProfile.retirement_account_id == account_id,
        or_(
            RetirementContributionProfile.effective_to.is_(None),
            RetirementContributionProfile.effective_to >= payload.effective_from,
        ),
    ]
    if payload.effective_to is not None:
        overlap_conditions.append(
            RetirementContributionProfile.effective_from <= payload.effective_to
        )
    overlap = await session.scalar(
        select(RetirementContributionProfile.id).where(and_(*overlap_conditions))
    )
    if overlap is not None:
        raise HTTPException(409, "Contribution profile dates overlap an existing profile")
    profile = RetirementContributionProfile(
        retirement_account_id=account_id, **payload.model_dump()
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.post(
    "/retirement-accounts/{account_id}/events",
    response_model=RetirementEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_retirement_event(
    account_id: uuid.UUID,
    payload: RetirementEventCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RetirementAccountEvent:
    await _account_with_access(account_id, HouseholdRole.EDITOR, user, session)
    if payload.idempotency_key is not None:
        duplicate = await session.scalar(
            select(RetirementAccountEvent.id).where(
                RetirementAccountEvent.retirement_account_id == account_id,
                RetirementAccountEvent.idempotency_key == payload.idempotency_key,
            )
        )
        if duplicate is not None:
            raise HTTPException(409, "Duplicate retirement event idempotency key")
    event = RetirementAccountEvent(retirement_account_id=account_id, **payload.model_dump())
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


@router.get("/retirement-accounts/{account_id}/projection", response_model=RetirementProjectionRead)
async def retirement_projection(
    account_id: uuid.UUID,
    projection_date: date = Query(),
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RetirementProjectionRead:
    account = await _account_with_access(account_id, HouseholdRole.VIEWER, user, session)
    profiles = list(
        await session.scalars(
            select(RetirementContributionProfile)
            .where(RetirementContributionProfile.retirement_account_id == account_id)
            .order_by(RetirementContributionProfile.effective_from)
        )
    )
    events = list(
        await session.scalars(
            select(RetirementAccountEvent)
            .where(RetirementAccountEvent.retirement_account_id == account_id)
            .order_by(RetirementAccountEvent.effective_date)
        )
    )
    australian_profile = await session.scalar(
        select(AustralianSuperProfile).where(
            AustralianSuperProfile.retirement_account_id == account_id
        )
    )
    annual_salary = Decimal("0")
    if account.person_id is not None:
        sources = list(
            await session.scalars(
                select(IncomeSource).where(
                    IncomeSource.person_id == account.person_id,
                    IncomeSource.taxable.is_(True),
                    IncomeSource.effective_from <= projection_date,
                    or_(
                        IncomeSource.effective_to.is_(None),
                        IncomeSource.effective_to >= projection_date,
                    ),
                )
            )
        )
        annual_salary = sum(
            (
                _annual_value(
                    source.gross_amount,
                    source.frequency,
                    source.annual_growth_rate,
                    source.effective_from,
                    projection_date,
                )
                for source in sources
            ),
            Decimal("0"),
        )
    try:
        entries, warnings = project_retirement(
            account.opening_balance,
            account.opening_balance_date,
            projection_date,
            account.expected_return_rate,
            account.annual_fees,
            annual_salary,
            [
                ContributionTerms(
                    effective_from=item.effective_from,
                    effective_to=item.effective_to,
                    employer_rate=item.employer_rate,
                    employer_amount=item.employer_amount,
                    voluntary_concessional_amount=item.voluntary_concessional_amount,
                    non_concessional_amount=item.non_concessional_amount,
                    contribution_tax_rate=item.contribution_tax_rate,
                    annual_cap=(
                        item.annual_cap
                        if item.annual_cap is not None
                        else (
                            australian_profile.concessional_cap
                            if australian_profile is not None
                            else None
                        )
                    ),
                    non_concessional_cap=(
                        australian_profile.non_concessional_cap
                        if australian_profile is not None
                        else None
                    ),
                )
                for item in profiles
            ],
            [(event.effective_date, event.amount) for event in events],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    projected = entries[-1].closing_balance if entries else money(account.opening_balance)
    total_contributions = sum(
        (
            entry.employer_contributions
            + entry.voluntary_concessional_contributions
            + entry.non_concessional_contributions
            for entry in entries
        ),
        Decimal("0"),
    )
    assumptions = [
        f"Expected return: {account.expected_return_rate}% per year, compounded monthly.",
        f"Fees: {account.annual_fees} per year, charged monthly.",
        "Employer-rate contributions use linked taxable income effective at the projection date.",
    ]
    if account.retirement_age is not None:
        assumptions.append(f"Planned retirement age: {account.retirement_age}.")
    if australian_profile is not None:
        assumptions.append(
            f"Australian super preservation age: {australian_profile.preservation_age}."
        )
    return RetirementProjectionRead(
        account_id=account.id,
        calculation_date=date.today(),
        projection_date=projection_date,
        currency=account.currency,
        entries=entries,
        projected_balance=projected,
        total_contributions=money(total_contributions),
        total_contribution_tax=money(
            sum((item.contribution_tax for item in entries), Decimal("0"))
        ),
        total_fees=money(sum((item.fees for item in entries), Decimal("0"))),
        total_earnings=money(sum((item.earnings for item in entries), Decimal("0"))),
        assumptions_used=assumptions,
        warnings=warnings + ["Projection is an estimate and does not include retirement drawdown."],
    )
