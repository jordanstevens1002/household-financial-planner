"""Income, tax, and household cash-flow API routes."""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.core.logging import get_logger
from app.income.schemas import (
    HouseholdCashflowRead,
    HouseholdExpenseCreate,
    HouseholdExpenseRead,
    IncomeSourceCreate,
    IncomeSourceRead,
    PersonIncomeProjection,
    TaxCalculationRead,
    TaxCalculationRequest,
    TaxProfileCreate,
    TaxProfileRead,
    TaxSettings,
)
from app.income.tax.base import TaxCalculationInput
from app.income.tax.registry import TaxProviderError, get_tax_engine, tax_year_for_date
from app.models import (
    ApplicationUser,
    Household,
    HouseholdExpense,
    HouseholdMembership,
    HouseholdRole,
    IncomeSource,
    PaymentFrequency,
    Person,
    PersonTaxProfile,
)
from app.properties.router import _validate_lookup

router = APIRouter(prefix="/api/v1", tags=["income and tax"])
logger = get_logger(component="income")

CENT = Decimal("0.01")
ANNUAL_MULTIPLIERS = {
    PaymentFrequency.WEEKLY: Decimal("52"),
    PaymentFrequency.FORTNIGHTLY: Decimal("26"),
    PaymentFrequency.MONTHLY: Decimal("12"),
    PaymentFrequency.QUARTERLY: Decimal("4"),
    PaymentFrequency.ANNUAL: Decimal("1"),
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _annual_value(
    amount: Decimal,
    frequency: PaymentFrequency,
    growth_rate: Decimal | None,
    effective_from: date,
    as_of: date,
) -> Decimal:
    if frequency == PaymentFrequency.ONCE:
        return amount if effective_from.year == as_of.year else Decimal("0")
    years = max(as_of.year - effective_from.year, 0)
    growth = Decimal("1") + (growth_rate or Decimal("0")) / Decimal("100")
    return amount * ANNUAL_MULTIPLIERS[frequency] * growth**years


async def _person_with_access(
    person_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> Person:
    result = await session.execute(
        select(Person, HouseholdMembership)
        .join(HouseholdMembership, HouseholdMembership.household_id == Person.household_id)
        .where(
            Person.id == person_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(404, "Person not found")
    person, membership = row
    assert isinstance(person, Person)
    assert isinstance(membership, HouseholdMembership)
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(403, "Insufficient household role")
    return person


@router.get("/people/{person_id}/income-sources", response_model=list[IncomeSourceRead])
async def list_income_sources(
    person_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[IncomeSource]:
    await _person_with_access(person_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(IncomeSource)
            .where(IncomeSource.person_id == person_id)
            .order_by(IncomeSource.effective_from)
        )
    )


@router.post(
    "/people/{person_id}/income-sources",
    response_model=IncomeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_income_source(
    person_id: uuid.UUID,
    payload: IncomeSourceCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> IncomeSource:
    await _person_with_access(person_id, HouseholdRole.EDITOR, user, session)
    await _validate_lookup(payload.income_type_id, "income_type", session)
    record = IncomeSource(person_id=person_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.info("income_source_created", person_id=str(person_id), source_id=str(record.id))
    return record


@router.get("/people/{person_id}/tax-profiles", response_model=list[TaxProfileRead])
async def list_tax_profiles(
    person_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PersonTaxProfile]:
    await _person_with_access(person_id, HouseholdRole.VIEWER, user, session)
    return list(
        await session.scalars(
            select(PersonTaxProfile)
            .where(PersonTaxProfile.person_id == person_id)
            .order_by(PersonTaxProfile.effective_from)
        )
    )


@router.post(
    "/people/{person_id}/tax-profiles",
    response_model=TaxProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_tax_profile(
    person_id: uuid.UUID,
    payload: TaxProfileCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PersonTaxProfile:
    await _person_with_access(person_id, HouseholdRole.EDITOR, user, session)
    settings = payload.settings.model_dump(mode="json")
    if payload.settings.calculation_mode == "AUTOMATIC":
        try:
            engine = get_tax_engine(payload.jurisdiction, payload.tax_year)
            settings["parameters"] = engine.validate_parameters(payload.settings.parameters)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    record = PersonTaxProfile(
        person_id=person_id,
        jurisdiction=payload.jurisdiction,
        tax_year=payload.tax_year,
        settings=settings,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


def _automatic_tax(
    jurisdiction: str, tax_year: str, gross: Decimal, settings: TaxSettings
) -> TaxCalculationRead:
    try:
        engine = get_tax_engine(jurisdiction, tax_year)
    except TaxProviderError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        result = engine.calculate(
            TaxCalculationInput(
                gross_taxable_income=gross,
                parameters=settings.parameters,
            )
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return TaxCalculationRead.model_validate(result, from_attributes=True)


@router.post("/calculations/tax", response_model=TaxCalculationRead)
async def calculate_tax(
    payload: TaxCalculationRequest,
    _: ApplicationUser = Depends(current_user),
) -> TaxCalculationRead:
    if payload.settings.calculation_mode == "MANUAL_NET":
        net = payload.settings.manual_annual_net_income
        assert net is not None
        total = max(payload.gross_taxable_income - net, Decimal("0"))
        return TaxCalculationRead(
            jurisdiction=payload.jurisdiction,
            tax_year=payload.tax_year,
            ruleset_version="manual",
            taxable_income=payload.gross_taxable_income,
            components=[],
            total=total,
            net_income=net,
            warnings=["Manual net income used; tax components are not calculated."],
        )
    return _automatic_tax(
        payload.jurisdiction, payload.tax_year, payload.gross_taxable_income, payload.settings
    )


@router.get("/households/{household_id}/expenses", response_model=list[HouseholdExpenseRead])
async def list_household_expenses(
    household_id: uuid.UUID,
    _: HouseholdMembership = Depends(require_household_role(HouseholdRole.VIEWER)),
    session: AsyncSession = Depends(get_session),
) -> list[HouseholdExpense]:
    return list(
        await session.scalars(
            select(HouseholdExpense)
            .where(HouseholdExpense.household_id == household_id)
            .order_by(HouseholdExpense.effective_from)
        )
    )


@router.post(
    "/households/{household_id}/expenses",
    response_model=HouseholdExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_household_expense(
    household_id: uuid.UUID,
    payload: HouseholdExpenseCreate,
    _: HouseholdMembership = Depends(require_household_role(HouseholdRole.EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> HouseholdExpense:
    await _validate_lookup(payload.category_id, "household_expense_type", session)
    if payload.person_id is not None:
        person = await session.get(Person, payload.person_id)
        if person is None or person.household_id != household_id:
            raise HTTPException(422, "Expense person must belong to the household")
    record = HouseholdExpense(household_id=household_id, **payload.model_dump())
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def _person_projection(
    person: Person, as_of: date, session: AsyncSession
) -> PersonIncomeProjection:
    sources = list(
        await session.scalars(
            select(IncomeSource).where(
                IncomeSource.person_id == person.id,
                IncomeSource.effective_from <= as_of,
                or_(IncomeSource.effective_to.is_(None), IncomeSource.effective_to >= as_of),
            )
        )
    )
    taxable = non_taxable = Decimal("0")
    for source in sources:
        annual = _annual_value(
            source.gross_amount,
            source.frequency,
            source.annual_growth_rate,
            source.effective_from,
            as_of,
        )
        sacrifice = _annual_value(
            source.salary_sacrifice_amount or Decimal("0"),
            source.frequency,
            source.annual_growth_rate,
            source.effective_from,
            as_of,
        )
        if source.taxable:
            taxable += max(annual - sacrifice, Decimal("0"))
        else:
            non_taxable += annual
    profile = await session.scalar(
        select(PersonTaxProfile)
        .where(
            PersonTaxProfile.person_id == person.id,
            PersonTaxProfile.effective_from <= as_of,
            or_(PersonTaxProfile.effective_to.is_(None), PersonTaxProfile.effective_to >= as_of),
        )
        .order_by(PersonTaxProfile.effective_from.desc())
    )
    if profile is None:
        return PersonIncomeProjection(
            person_id=person.id,
            display_name=person.display_name,
            gross_taxable_income=_money(taxable),
            non_taxable_income=_money(non_taxable),
            net_income=_money(taxable + non_taxable),
            tax_and_repayments=Decimal("0.00"),
            calculation_mode="NO_PROFILE",
            warnings=["No effective tax profile; gross taxable income is shown as net."],
        )
    settings = TaxSettings.model_validate(profile.settings)
    if settings.calculation_mode == "MANUAL_NET":
        assert settings.manual_annual_net_income is not None
        net = settings.manual_annual_net_income + non_taxable
        return PersonIncomeProjection(
            person_id=person.id,
            display_name=person.display_name,
            gross_taxable_income=_money(taxable),
            non_taxable_income=_money(non_taxable),
            net_income=_money(net),
            tax_and_repayments=_money(
                max(taxable - settings.manual_annual_net_income, Decimal("0"))
            ),
            calculation_mode="MANUAL_NET",
            warnings=["Manual net income used; tax components are not calculated."],
        )
    try:
        expected_tax_year = tax_year_for_date(profile.jurisdiction, as_of)
    except TaxProviderError as exc:
        return PersonIncomeProjection(
            person_id=person.id,
            display_name=person.display_name,
            gross_taxable_income=_money(taxable),
            non_taxable_income=_money(non_taxable),
            net_income=_money(taxable + non_taxable),
            tax_and_repayments=Decimal("0.00"),
            calculation_mode="NO_PROFILE",
            warnings=[f"{exc}; gross taxable income is shown as net."],
        )
    if profile.tax_year != expected_tax_year:
        return PersonIncomeProjection(
            person_id=person.id,
            display_name=person.display_name,
            gross_taxable_income=_money(taxable),
            non_taxable_income=_money(non_taxable),
            net_income=_money(taxable + non_taxable),
            tax_and_repayments=Decimal("0.00"),
            calculation_mode="NO_PROFILE",
            warnings=[
                f"No automatic tax profile for {expected_tax_year}; gross taxable income "
                "is shown as net."
            ],
        )
    tax = _automatic_tax(profile.jurisdiction, profile.tax_year, taxable, settings)
    return PersonIncomeProjection(
        person_id=person.id,
        display_name=person.display_name,
        gross_taxable_income=_money(taxable),
        non_taxable_income=_money(non_taxable),
        net_income=_money(tax.net_income + non_taxable),
        tax_and_repayments=tax.total,
        calculation_mode="AUTOMATIC",
        warnings=tax.warnings,
    )


@router.get("/households/{household_id}/income-projection", response_model=HouseholdCashflowRead)
@router.get("/households/{household_id}/cashflow", response_model=HouseholdCashflowRead)
async def household_cashflow(
    household_id: uuid.UUID,
    _: HouseholdMembership = Depends(require_household_role(HouseholdRole.VIEWER)),
    as_of: date = Query(),
    session: AsyncSession = Depends(get_session),
) -> HouseholdCashflowRead:
    household = await session.get(Household, household_id)
    assert household is not None
    people = list(
        await session.scalars(
            select(Person).where(
                Person.household_id == household_id,
                Person.is_active.is_(True),
                Person.effective_from <= as_of,
                or_(Person.effective_to.is_(None), Person.effective_to >= as_of),
            )
        )
    )
    projections = [await _person_projection(person, as_of, session) for person in people]
    expenses = list(
        await session.scalars(
            select(HouseholdExpense).where(
                HouseholdExpense.household_id == household_id,
                HouseholdExpense.effective_from <= as_of,
                or_(
                    HouseholdExpense.effective_to.is_(None),
                    HouseholdExpense.effective_to >= as_of,
                ),
            )
        )
    )
    annual_expenses = sum(
        (
            _annual_value(
                item.amount,
                item.frequency,
                item.annual_growth_rate,
                item.effective_from,
                as_of,
            )
            for item in expenses
        ),
        Decimal("0"),
    )
    gross = sum(
        (item.gross_taxable_income + item.non_taxable_income for item in projections),
        Decimal("0"),
    )
    net = sum((item.net_income for item in projections), Decimal("0"))
    warnings = [warning for item in projections for warning in item.warnings]
    return HouseholdCashflowRead(
        household_id=household_id,
        as_of=as_of,
        currency=household.currency,
        people=projections,
        annual_gross_income=_money(gross),
        annual_net_income=_money(net),
        annual_expenses=_money(annual_expenses),
        annual_surplus=_money(net - annual_expenses),
        monthly_net_income=_money(net / Decimal("12")),
        monthly_expenses=_money(annual_expenses / Decimal("12")),
        monthly_surplus=_money((net - annual_expenses) / Decimal("12")),
        warnings=warnings,
    )
