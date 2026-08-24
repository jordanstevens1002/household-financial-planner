"""Income, tax, and household cash-flow API routes."""

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.core.logging import get_logger
from app.income.schemas import (
    HouseholdCashflowRead,
    HouseholdExpenseCreate,
    HouseholdExpenseRead,
    HouseholdExpenseUpdate,
    IncomeSourceCreate,
    IncomeSourceRead,
    LoanRepaymentAllocationRead,
    LoanRepaymentProjectionRead,
    PersonIncomeProjection,
    StandaloneTaxCalculationRead,
    TaxCalculationRead,
    TaxCalculationRequest,
    TaxProfileCreate,
    TaxProfileRead,
    TaxProviderRead,
    TaxSettings,
)
from app.income.tax.base import TaxCalculationInput
from app.income.tax.registry import (
    TaxProviderError,
    get_registry,
    get_tax_engine,
    get_tax_engine_for_date,
)
from app.loans.calculations import generate_schedule, payments_per_year
from app.loans.service import equal_borrower_allocations
from app.models import (
    ApplicationUser,
    EventType,
    FinancialEvent,
    Household,
    HouseholdExpense,
    HouseholdMembership,
    HouseholdRole,
    IncomeSource,
    Loan,
    LoanBorrower,
    LoanRepaymentResponsibility,
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


async def _loan_repayment_projection(
    loan: Loan,
    household_currency: str,
    people_by_id: dict[uuid.UUID, Person],
    as_of: date,
    session: AsyncSession,
) -> LoanRepaymentProjectionRead | None:
    if loan.opening_balance_date > as_of:
        return None
    typed_events = list(
        (
            await session.execute(
                select(FinancialEvent, EventType.code)
                .join(EventType, EventType.id == FinancialEvent.event_type_id)
                .where(
                    FinancialEvent.loan_id == loan.id,
                    FinancialEvent.is_enabled.is_(True),
                )
                .order_by(
                    FinancialEvent.effective_at,
                    EventType.priority,
                    FinancialEvent.recorded_at,
                    FinancialEvent.id,
                )
            )
        ).all()
    )
    effective_events = [
        (event, code) for event, code in typed_events if event.effective_at.date() <= as_of
    ]
    closure_codes = {"LOAN_REFINANCED", "LOAN_CLOSED"}
    is_closed = any(code in closure_codes for _, code in effective_events)
    has_later_closure = any(
        code in closure_codes and event.effective_at.date() > as_of for event, code in typed_events
    )
    if is_closed or (not loan.is_active and not has_later_closure):
        return None
    warnings: list[str] = []
    try:
        schedule = generate_schedule(
            loan,
            effective_events,
            through_date=as_of + timedelta(days=35),
        )
        next_entry = next(
            (entry for entry in schedule.entries if entry.payment_date >= as_of),
            None,
        )
        periodic = next_entry.repayment if next_entry is not None else Decimal("0")
    except ValueError as exc:
        periodic = Decimal("0")
        warnings.append(f"{loan.display_name}: {exc}; repayment is excluded from cash flow.")
    annual = _money(periodic * Decimal(payments_per_year(loan.repayment_frequency)))
    included = loan.currency == household_currency
    if not included:
        warnings.append(
            f"{loan.display_name} uses {loan.currency}; no exchange rate is configured, "
            f"so its repayment is excluded from the {household_currency} household total."
        )
    latest_responsibility_date = (
        select(func.max(LoanRepaymentResponsibility.effective_from))
        .where(
            LoanRepaymentResponsibility.loan_id == loan.id,
            LoanRepaymentResponsibility.effective_from <= as_of,
        )
        .scalar_subquery()
    )
    responsibilities = list(
        await session.scalars(
            select(LoanRepaymentResponsibility).where(
                LoanRepaymentResponsibility.loan_id == loan.id,
                LoanRepaymentResponsibility.effective_from == latest_responsibility_date,
                or_(
                    LoanRepaymentResponsibility.effective_to.is_(None),
                    LoanRepaymentResponsibility.effective_to >= as_of,
                ),
            )
        )
    )
    allocations_by_person: dict[uuid.UUID, Decimal] = {}
    for item in responsibilities:
        allocations_by_person[item.person_id] = (
            allocations_by_person.get(item.person_id, Decimal("0")) + item.responsibility_percentage
        )
    responsibility_total = sum(allocations_by_person.values(), Decimal("0"))
    if responsibilities and responsibility_total != Decimal("100"):
        warnings.append(
            f"{loan.display_name} repayment responsibility totals "
            f"{responsibility_total:.2f}% rather than 100.00%."
        )
    if not responsibilities:
        borrower_ids = list(
            await session.scalars(
                select(LoanBorrower.person_id)
                .where(LoanBorrower.loan_id == loan.id)
                .order_by(LoanBorrower.person_id)
            )
        )
        allocations_by_person = equal_borrower_allocations(borrower_ids)
        if not borrower_ids:
            warnings.append(
                f"{loan.display_name} has no named borrowers; its repayment remains "
                "a whole-household expense."
            )
    responsibility_people = dict(people_by_id)
    inactive_person_ids = {
        person_id for person_id in allocations_by_person if person_id not in responsibility_people
    }
    if inactive_person_ids:
        responsibility_people.update(
            {
                person.id: person
                for person in await session.scalars(
                    select(Person).where(Person.id.in_(inactive_person_ids))
                )
            }
        )
        inactive_names = [
            responsibility_people[person_id].display_name
            for person_id in inactive_person_ids
            if person_id in responsibility_people
        ]
        if inactive_names:
            warnings.append(
                f"{loan.display_name} has repayment responsibility assigned to "
                f"inactive people at {as_of.isoformat()}: {', '.join(sorted(inactive_names))}."
            )
    allocations = [
        LoanRepaymentAllocationRead(
            person_id=person_id,
            display_name=responsibility_people[person_id].display_name,
            responsibility_percentage=percentage,
            annual_amount=_money(annual * percentage / Decimal("100")),
            monthly_amount=_money(annual * percentage / Decimal("100") / Decimal("12")),
        )
        for person_id, percentage in allocations_by_person.items()
        if person_id in responsibility_people
    ]
    return LoanRepaymentProjectionRead(
        loan_id=loan.id,
        property_id=loan.property_id,
        display_name=loan.display_name,
        currency=loan.currency,
        repayment_frequency=loan.repayment_frequency,
        periodic_repayment=_money(periodic),
        annual_repayment=annual,
        monthly_repayment=_money(annual / Decimal("12")),
        included_in_household_total=included,
        allocations=allocations,
        warnings=warnings,
    )


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
            .where(
                PersonTaxProfile.person_id == person_id,
                PersonTaxProfile.superseded_at.is_(None),
            )
            .order_by(PersonTaxProfile.effective_from)
        )
    )


@router.get("/tax-providers", response_model=list[TaxProviderRead])
async def list_tax_providers(
    _: ApplicationUser = Depends(current_user),
) -> list[TaxProviderRead]:
    return [
        TaxProviderRead(
            jurisdiction=provider.jurisdiction,
            display_name=provider.display_name,
            supported_tax_years=list(provider.supported_tax_years),
        )
        for provider in get_registry().providers()
    ]


@router.post(
    "/people/{person_id}/tax-profiles",
    response_model=TaxProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_tax_profile(
    person_id: uuid.UUID,
    payload: TaxProfileCreate,
    response: Response,
    replace_existing: bool = Query(False),
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
    existing = await session.scalar(
        select(PersonTaxProfile)
        .where(
            PersonTaxProfile.person_id == person_id,
            PersonTaxProfile.effective_from == payload.effective_from,
            PersonTaxProfile.superseded_at.is_(None),
        )
        .with_for_update()
    )
    if existing is not None and not replace_existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tax settings already exist for this effective date; confirm replacement",
        )
    record = existing or PersonTaxProfile(person_id=person_id)
    record.jurisdiction = payload.jurisdiction
    record.tax_year = payload.tax_year
    record.settings = settings
    record.effective_from = payload.effective_from
    record.effective_to = payload.effective_to
    session.add(record)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Tax settings already exist for this effective date; confirm replacement",
        ) from exc
    await session.refresh(record)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
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


@router.post("/calculations/tax", response_model=StandaloneTaxCalculationRead)
async def calculate_tax(
    payload: TaxCalculationRequest,
    _: ApplicationUser = Depends(current_user),
) -> StandaloneTaxCalculationRead:
    if payload.settings.calculation_mode == "MANUAL_NET":
        net = payload.settings.manual_annual_net_income
        assert net is not None
        total = max(payload.gross_taxable_income - net, Decimal("0"))
        return StandaloneTaxCalculationRead(
            currency=payload.currency,
            jurisdiction=payload.jurisdiction,
            tax_year=payload.tax_year,
            ruleset_version="manual",
            taxable_income=payload.gross_taxable_income,
            components=[],
            total=total,
            net_income=net,
            warnings=["Manual net income used; tax components are not calculated."],
        )
    result = _automatic_tax(
        payload.jurisdiction, payload.tax_year, payload.gross_taxable_income, payload.settings
    )
    return StandaloneTaxCalculationRead(currency=payload.currency, **result.model_dump())


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
    actor: HouseholdMembership = Depends(require_household_role(HouseholdRole.EDITOR)),
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
    logger.info(
        "household_expense_created",
        actor_user_id=str(actor.application_user_id),
        household_id=str(household_id),
        expense_id=str(record.id),
        resulting_amount=str(record.amount),
    )
    return record


async def _household_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    session: AsyncSession,
) -> HouseholdExpense:
    expense = await session.get(HouseholdExpense, expense_id)
    if expense is None or expense.household_id != household_id:
        raise HTTPException(404, "Household expense not found")
    return expense


async def _validate_expense_person(
    household_id: uuid.UUID,
    person_id: uuid.UUID | None,
    session: AsyncSession,
) -> None:
    if person_id is None:
        return
    person = await session.get(Person, person_id)
    if person is None or person.household_id != household_id:
        raise HTTPException(422, "Expense person must belong to the household")


@router.patch(
    "/households/{household_id}/expenses/{expense_id}",
    response_model=HouseholdExpenseRead,
)
async def update_household_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    payload: HouseholdExpenseUpdate,
    actor: HouseholdMembership = Depends(require_household_role(HouseholdRole.EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> HouseholdExpense:
    expense = await _household_expense(household_id, expense_id, session)
    await _validate_lookup(payload.category_id, "household_expense_type", session)
    await _validate_expense_person(household_id, payload.person_id, session)
    previous_amount = expense.amount
    previous_effective_to = expense.effective_to
    for field, value in payload.model_dump().items():
        setattr(expense, field, value)
    await session.commit()
    await session.refresh(expense)
    logger.info(
        "household_expense_updated",
        actor_user_id=str(actor.application_user_id),
        household_id=str(household_id),
        expense_id=str(expense_id),
        previous_amount=str(previous_amount),
        resulting_amount=str(expense.amount),
        previous_effective_to=str(previous_effective_to),
        resulting_effective_to=str(expense.effective_to),
    )
    return expense


@router.delete(
    "/households/{household_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_household_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    actor: HouseholdMembership = Depends(require_household_role(HouseholdRole.EDITOR)),
    session: AsyncSession = Depends(get_session),
) -> None:
    expense = await _household_expense(household_id, expense_id, session)
    display_name = expense.display_name
    amount = expense.amount
    await session.delete(expense)
    await session.commit()
    logger.info(
        "household_expense_deleted",
        actor_user_id=str(actor.application_user_id),
        household_id=str(household_id),
        expense_id=str(expense_id),
        display_name=display_name,
        previous_amount=str(amount),
        resulting_amount=None,
    )


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
            PersonTaxProfile.superseded_at.is_(None),
            PersonTaxProfile.effective_from <= as_of,
            or_(PersonTaxProfile.effective_to.is_(None), PersonTaxProfile.effective_to >= as_of),
        )
        .order_by(PersonTaxProfile.effective_from.desc(), PersonTaxProfile.id.desc())
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
        engine, expected_tax_year, uses_fallback = get_tax_engine_for_date(
            profile.jurisdiction, as_of
        )
        parameters = engine.validate_parameters(settings.parameters)
        tax_result = engine.calculate(
            TaxCalculationInput(
                gross_taxable_income=taxable,
                parameters=parameters,
            )
        )
        tax = TaxCalculationRead.model_validate(tax_result, from_attributes=True)
    except (TaxProviderError, ValueError) as exc:
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
    warnings = list(tax.warnings)
    if uses_fallback:
        warnings.insert(
            0,
            f"No {expected_tax_year} tax rules are installed for {profile.jurisdiction}; "
            f"using {tax.tax_year} rules as the latest available planning fallback.",
        )
    return PersonIncomeProjection(
        person_id=person.id,
        display_name=person.display_name,
        gross_taxable_income=_money(taxable),
        non_taxable_income=_money(non_taxable),
        net_income=_money(tax.net_income + non_taxable),
        tax_and_repayments=tax.total,
        calculation_mode="AUTOMATIC",
        warnings=warnings,
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
    people_by_id = {person.id: person for person in people}
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
    annual_ordinary_expenses = sum(
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
    loans = list(
        await session.scalars(
            select(Loan).where(
                Loan.household_id == household_id,
                Loan.opening_balance_date <= as_of,
            )
        )
    )
    loan_repayments = [
        projection
        for loan in loans
        if (
            projection := await _loan_repayment_projection(
                loan,
                household.currency,
                people_by_id,
                as_of,
                session,
            )
        )
        is not None
    ]
    annual_loan_repayments = sum(
        (item.annual_repayment for item in loan_repayments if item.included_in_household_total),
        Decimal("0"),
    )
    annual_expenses = annual_ordinary_expenses + annual_loan_repayments
    gross = sum(
        (item.gross_taxable_income + item.non_taxable_income for item in projections),
        Decimal("0"),
    )
    net = sum((item.net_income for item in projections), Decimal("0"))
    warnings = [
        *[warning for item in projections for warning in item.warnings],
        *[warning for item in loan_repayments for warning in item.warnings],
    ]
    return HouseholdCashflowRead(
        household_id=household_id,
        as_of=as_of,
        currency=household.currency,
        people=projections,
        annual_gross_income=_money(gross),
        annual_net_income=_money(net),
        annual_ordinary_expenses=_money(annual_ordinary_expenses),
        annual_loan_repayments=_money(annual_loan_repayments),
        annual_expenses=_money(annual_expenses),
        annual_surplus=_money(net - annual_expenses),
        monthly_net_income=_money(net / Decimal("12")),
        monthly_ordinary_expenses=_money(annual_ordinary_expenses / Decimal("12")),
        monthly_loan_repayments=_money(annual_loan_repayments / Decimal("12")),
        monthly_expenses=_money(annual_expenses / Decimal("12")),
        monthly_surplus=_money((net - annual_expenses) / Decimal("12")),
        loan_repayments=loan_repayments,
        warnings=warnings,
    )
