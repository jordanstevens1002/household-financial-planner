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
from app.retirement_providers.base import RetirementProjectionRules
from app.retirement_providers.registry import (
    RetirementProviderError,
    get_retirement_provider,
)
from app.retirement_schemas import (
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


def _provider_settings(
    provider_code: str | None,
    settings: dict[str, object],
    account_type_code: str,
) -> dict[str, object]:
    if provider_code is None:
        return settings
    try:
        provider = get_retirement_provider(provider_code)
        provider.validate_account_type(account_type_code)
        return provider.validate_settings(settings)
    except (RetirementProviderError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get(
    "/households/{household_id}/retirement-accounts",
    response_model=list[RetirementAccountRead],
)
async def list_retirement_accounts(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[RetirementAccount]:
    accounts = list(
        await session.scalars(
            select(RetirementAccount).where(RetirementAccount.household_id == household_id)
        )
    )
    return accounts


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
) -> RetirementAccount:
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
    values = payload.model_dump()
    values["currency"] = payload.currency or household.currency
    values["provider_settings"] = _provider_settings(
        payload.provider_code, payload.provider_settings, account_type.code
    )
    account = RetirementAccount(household_id=household_id, **values)
    session.add(account)
    await session.commit()
    await session.refresh(account)
    logger.info("retirement_account_created", account_id=str(account.id))
    return account


@router.put("/retirement-accounts/{account_id}", response_model=RetirementAccountRead)
async def update_retirement_account(
    account_id: uuid.UUID,
    payload: RetirementAccountUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RetirementAccount:
    account = await _account_with_access(account_id, HouseholdRole.EDITOR, user, session)
    account_type = await session.get(LookupItem, account.account_type_id)
    assert account_type is not None
    values = payload.model_dump()
    values["provider_settings"] = _provider_settings(
        payload.provider_code, payload.provider_settings, account_type.code
    )
    for name, value in values.items():
        setattr(account, name, value)
    await session.commit()
    await session.refresh(account)
    return account


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
    rules = RetirementProjectionRules()
    if account.provider_code is not None:
        try:
            rules = get_retirement_provider(account.provider_code).projection_rules(
                projection_date, account.provider_settings
            )
        except (RetirementProviderError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
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
                    voluntary_pre_tax_amount=item.voluntary_pre_tax_amount,
                    voluntary_post_tax_amount=item.voluntary_post_tax_amount,
                    contribution_tax_rate=item.contribution_tax_rate,
                    annual_pre_tax_cap=(
                        item.annual_pre_tax_cap
                        if item.annual_pre_tax_cap is not None
                        else (rules.annual_pre_tax_cap)
                    ),
                    annual_post_tax_cap=rules.annual_post_tax_cap,
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
            + entry.voluntary_pre_tax_contributions
            + entry.voluntary_post_tax_contributions
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
    assumptions.extend(rules.assumptions)
    return RetirementProjectionRead(
        account_id=account.id,
        calculation_date=date.today(),
        projection_date=projection_date,
        currency=account.currency,
        provider_code=account.provider_code,
        entries=entries,
        projected_balance=projected,
        total_contributions=money(total_contributions),
        total_contribution_tax=money(
            sum((item.contribution_tax for item in entries), Decimal("0"))
        ),
        total_fees=money(sum((item.fees for item in entries), Decimal("0"))),
        total_earnings=money(sum((item.earnings for item in entries), Decimal("0"))),
        assumptions_used=assumptions,
        warnings=rules.warnings
        + warnings
        + ["Projection is an estimate and does not include retirement drawdown."],
    )
