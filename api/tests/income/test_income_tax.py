"""Income and tax API tests."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.income.tax.australia import AustraliaTaxEngine2025_26
from app.income.tax.base import TaxCalculationInput, TaxEstimate
from app.models import Household, LookupItem, Person
from tests.households.test_households import create_household


@pytest.fixture
async def finance_lookups(session: AsyncSession) -> dict[str, LookupItem]:
    salary = LookupItem(
        category="income_type", code="SALARY_TEST", display_name="Salary", is_active=True
    )
    bonus = LookupItem(
        category="income_type", code="BONUS_TEST", display_name="Bonus", is_active=True
    )
    payment = LookupItem(
        category="income_type",
        code="NON_TAXABLE_TEST",
        display_name="Non-taxable payment",
        is_active=True,
    )
    expense = LookupItem(
        category="household_expense_type",
        code="LIVING_TEST",
        display_name="Living costs",
        is_active=True,
    )
    session.add_all([salary, bonus, payment, expense])
    await session.commit()
    return {"salary": salary, "bonus": bonus, "payment": payment, "expense": expense}


async def create_person(client: AsyncClient) -> tuple[dict[str, str], dict[str, str]]:
    household = await create_household(client)
    response = await client.post(
        f"/api/v1/households/{household['id']}/people",
        json={"display_name": "Alex", "effective_from": "2020-01-01"},
    )
    assert response.status_code == 201
    return household, response.json()


def income_payload(
    lookup: LookupItem,
    name: str,
    amount: int,
    frequency: str,
    taxable: bool = True,
) -> dict[str, object]:
    return {
        "income_type_id": str(lookup.id),
        "display_name": name,
        "gross_amount": amount,
        "frequency": frequency,
        "effective_from": "2025-01-01",
        "taxable": taxable,
    }


def tax_input(gross: int, **parameters: object) -> TaxCalculationInput:
    return TaxCalculationInput(gross_taxable_income=gross, parameters=parameters)


def components(result: TaxEstimate) -> dict[str, object]:
    return {item.code: item.amount for item in result.components}


def test_australian_2025_26_tax_engine_includes_lito_medicare_and_help() -> None:
    engine = AustraliaTaxEngine2025_26()
    low = engine.calculate(tax_input(45_000))
    assert components(low)["income_tax"] == 4_288
    assert components(low)["low_income_tax_offset"] == -325
    assert components(low)["medicare_levy"] == 900
    assert low.total == 4_863

    help_result = engine.calculate(tax_input(100_000, has_study_loan=True))
    assert components(help_result)["income_tax"] == 20_788
    assert components(help_result)["study_loan_repayment"] == 4_950
    assert help_result.total == 27_738
    assert help_result.net_income == 72_262


def test_foreign_resident_has_no_tax_free_threshold_or_medicare() -> None:
    result = AustraliaTaxEngine2025_26().calculate(tax_input(100_000, resident=False))
    assert components(result)["income_tax"] == 30_000
    assert components(result)["medicare_levy"] == 0
    assert result.net_income == 70_000


@pytest.mark.parametrize(
    ("income", "expected_tax"),
    [
        (0, 0),
        (18_200, 0),
        (45_000, 3_963),
        (135_000, 31_288),
        (190_000, 51_638),
        (200_000, 56_138),
    ],
)
def test_resident_income_tax_bracket_boundaries(income: int, expected_tax: int) -> None:
    result = AustraliaTaxEngine2025_26().calculate(tax_input(income, include_medicare_levy=False))
    calculated = components(result)
    assert calculated["income_tax"] + calculated["low_income_tax_offset"] == expected_tax


@pytest.mark.parametrize(
    ("income", "expected_tax"),
    [(135_000, 40_500), (190_000, 60_850), (200_000, 65_350)],
)
def test_foreign_resident_tax_bracket_boundaries(income: int, expected_tax: int) -> None:
    result = AustraliaTaxEngine2025_26().calculate(tax_input(income, resident=False))
    assert components(result)["income_tax"] == expected_tax


@pytest.mark.parametrize(
    ("income", "expected_repayment"),
    [(67_000, 0), (100_000, 4_950), (150_000, 12_950), (180_000, 18_000)],
)
def test_2025_26_study_loan_marginal_tiers(income: int, expected_repayment: int) -> None:
    result = AustraliaTaxEngine2025_26().calculate(
        tax_input(income, include_medicare_levy=False, has_study_loan=True)
    )
    assert components(result)["study_loan_repayment"] == expected_repayment


def test_deductions_and_medicare_surcharge_are_explicit_inputs() -> None:
    result = AustraliaTaxEngine2025_26().calculate(
        tax_input(
            100_000,
            deductions=10_000,
            include_medicare_levy=False,
            medicare_levy_surcharge_rate=1,
        )
    )
    assert result.taxable_income == 90_000
    assert components(result)["medicare_levy"] == 0
    assert components(result)["medicare_levy_surcharge"] == 900


async def test_multiple_dated_income_sources_and_manual_net_household_cashflow(
    client: AsyncClient, finance_lookups: dict[str, LookupItem]
) -> None:
    household, person = await create_person(client)
    salary = income_payload(finance_lookups["salary"], "Main job", 2_000, "WEEKLY") | {
        "salary_sacrifice_amount": 100
    }
    bonus = income_payload(finance_lookups["bonus"], "Bonus", 1_000, "MONTHLY")
    payment = income_payload(
        finance_lookups["payment"], "Support payment", 5_000, "ANNUAL", taxable=False
    )
    for payload in (salary, bonus, payment):
        response = await client.post(f"/api/v1/people/{person['id']}/income-sources", json=payload)
        assert response.status_code == 201
    profile = await client.post(
        f"/api/v1/people/{person['id']}/tax-profiles",
        json={
            "jurisdiction": "AU",
            "tax_year": "2025-26",
            "effective_from": "2025-07-01",
            "settings": {
                "calculation_mode": "MANUAL_NET",
                "manual_annual_net_income": 80_000,
            },
        },
    )
    assert profile.status_code == 201
    expense = await client.post(
        f"/api/v1/households/{household['id']}/expenses",
        json={
            "category_id": str(finance_lookups["expense"].id),
            "display_name": "Living costs",
            "amount": 2_000,
            "frequency": "MONTHLY",
            "effective_from": "2025-01-01",
            "is_essential": True,
        },
    )
    assert expense.status_code == 201
    result = await client.get(
        f"/api/v1/households/{household['id']}/cashflow", params={"as_of": "2025-07-01"}
    )
    assert result.status_code == 200
    body = result.json()
    assert body["annual_gross_income"] == "115800.00"
    assert body["annual_net_income"] == "85000.00"
    assert body["annual_expenses"] == "24000.00"
    assert body["annual_surplus"] == "61000.00"
    assert body["monthly_surplus"] == "5083.33"
    assert body["people"][0]["calculation_mode"] == "MANUAL_NET"


async def test_automatic_tax_profile_drives_income_projection(
    client: AsyncClient, finance_lookups: dict[str, LookupItem]
) -> None:
    household, person = await create_person(client)
    await client.post(
        f"/api/v1/people/{person['id']}/income-sources",
        json=income_payload(finance_lookups["salary"], "Salary", 100_000, "ANNUAL"),
    )
    await client.post(
        f"/api/v1/people/{person['id']}/tax-profiles",
        json={
            "jurisdiction": "AU",
            "tax_year": "2025-26",
            "effective_from": "2025-07-01",
            "settings": {"parameters": {"has_study_loan": True}},
        },
    )
    body = (
        await client.get(
            f"/api/v1/households/{household['id']}/income-projection",
            params={"as_of": "2025-07-01"},
        )
    ).json()
    assert body["annual_net_income"] == "72262.00"
    assert body["people"][0]["tax_and_repayments"] == "27738.00"
    assert body["people"][0]["calculation_mode"] == "AUTOMATIC"


async def test_automatic_tax_profile_is_not_reused_for_a_later_financial_year(
    client: AsyncClient, finance_lookups: dict[str, LookupItem]
) -> None:
    household, person = await create_person(client)
    await client.post(
        f"/api/v1/people/{person['id']}/income-sources",
        json=income_payload(finance_lookups["salary"], "Salary", 100_000, "ANNUAL"),
    )
    await client.post(
        f"/api/v1/people/{person['id']}/tax-profiles",
        json={
            "jurisdiction": "AU",
            "tax_year": "2025-26",
            "effective_from": "2025-07-01",
            "settings": {},
        },
    )
    body = (
        await client.get(
            f"/api/v1/households/{household['id']}/cashflow",
            params={"as_of": "2026-07-01"},
        )
    ).json()
    assert body["people"][0]["calculation_mode"] == "NO_PROFILE"
    assert "2026-27" in body["people"][0]["warnings"][0]


async def test_tax_calculation_rejects_unsupported_year_and_accepts_manual_net(
    client: AsyncClient,
) -> None:
    unsupported = await client.post(
        "/api/v1/calculations/tax",
        json={"jurisdiction": "AU", "tax_year": "2026-27", "gross_taxable_income": 80_000},
    )
    assert unsupported.status_code == 422
    manual = await client.post(
        "/api/v1/calculations/tax",
        json={
            "jurisdiction": "NZ",
            "tax_year": "2025-26",
            "gross_taxable_income": 80_000,
            "settings": {
                "calculation_mode": "MANUAL_NET",
                "manual_annual_net_income": 65_000,
            },
        },
    )
    assert manual.status_code == 200
    assert manual.json()["net_income"] == "65000"
    assert "Manual net income" in manual.json()["warnings"][0]


async def test_australian_provider_rejects_unknown_country_parameters(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/calculations/tax",
        json={
            "jurisdiction": "au",
            "tax_year": "2025-26",
            "gross_taxable_income": 80_000,
            "settings": {"parameters": {"not_an_australian_parameter": True}},
        },
    )

    assert response.status_code == 422
    assert "not_an_australian_parameter" in response.json()["detail"]


async def test_future_and_ended_income_do_not_leak_into_snapshot(
    client: AsyncClient, finance_lookups: dict[str, LookupItem]
) -> None:
    household, person = await create_person(client)
    ended = income_payload(finance_lookups["salary"], "Old job", 70_000, "ANNUAL") | {
        "effective_from": "2023-01-01",
        "effective_to": "2024-12-31",
    }
    future = income_payload(finance_lookups["salary"], "Future job", 90_000, "ANNUAL") | {
        "effective_from": "2026-01-01"
    }
    for payload in (ended, future):
        assert (
            await client.post(f"/api/v1/people/{person['id']}/income-sources", json=payload)
        ).status_code == 201
    body = (
        await client.get(
            f"/api/v1/households/{household['id']}/cashflow",
            params={"as_of": "2025-07-01"},
        )
    ).json()
    assert body["annual_gross_income"] == "0.00"


async def test_income_and_expense_growth_apply_to_future_snapshots(
    client: AsyncClient, finance_lookups: dict[str, LookupItem]
) -> None:
    household, person = await create_person(client)
    source = income_payload(finance_lookups["salary"], "Growing income", 1_000, "ANNUAL") | {
        "annual_growth_rate": 10
    }
    await client.post(f"/api/v1/people/{person['id']}/income-sources", json=source)
    await client.post(
        f"/api/v1/households/{household['id']}/expenses",
        json={
            "category_id": str(finance_lookups["expense"].id),
            "display_name": "Growing costs",
            "amount": 1_200,
            "frequency": "ANNUAL",
            "annual_growth_rate": 10,
            "effective_from": "2025-01-01",
            "is_essential": True,
        },
    )
    body = (
        await client.get(
            f"/api/v1/households/{household['id']}/cashflow",
            params={"as_of": "2026-07-01"},
        )
    ).json()
    assert body["annual_gross_income"] == "1100.00"
    assert body["annual_expenses"] == "1320.00"
    assert body["annual_surplus"] == "-220.00"


async def test_zero_person_household_has_zero_cashflow(client: AsyncClient) -> None:
    household = await create_household(client)
    body = (
        await client.get(
            f"/api/v1/households/{household['id']}/cashflow",
            params={"as_of": "2025-07-01"},
        )
    ).json()
    assert body["people"] == []
    assert body["annual_net_income"] == "0.00"
    assert body["annual_surplus"] == "0.00"


async def test_cross_household_people_and_expense_people_are_rejected(
    client: AsyncClient,
    session: AsyncSession,
    finance_lookups: dict[str, LookupItem],
) -> None:
    household, _ = await create_person(client)
    other_household = Household(display_name="Other", currency="NZD")
    session.add(other_household)
    await session.flush()
    hidden_person = Person(
        household_id=other_household.id,
        display_name="Hidden",
        is_active=True,
        effective_from=date(2020, 1, 1),
    )
    session.add(hidden_person)
    await session.commit()
    assert (
        await client.get(f"/api/v1/people/{hidden_person.id}/income-sources")
    ).status_code == 404
    expense = await client.post(
        f"/api/v1/households/{household['id']}/expenses",
        json={
            "person_id": str(hidden_person.id),
            "category_id": str(finance_lookups["expense"].id),
            "display_name": "Invalid",
            "amount": 10,
            "frequency": "MONTHLY",
            "effective_from": "2025-01-01",
            "is_essential": False,
        },
    )
    assert expense.status_code == 422
