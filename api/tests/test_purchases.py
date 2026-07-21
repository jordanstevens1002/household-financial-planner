from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Household, LookupItem, Person, PurchasePlan
from app.purchase_calculations import calculate_feasibility, monthly_repayment
from tests.test_households import create_household


def test_feasibility_calculation_applies_funding_and_comfort_thresholds() -> None:
    result = calculate_feasibility(
        purchase_price=Decimal("500000"),
        total_costs=Decimal("27000"),
        desired_buffer=Decimal("10000"),
        equity_funding=Decimal("100000"),
        borrowed_funding=Decimal("0"),
        maximum_additional_borrowing=Decimal("450000"),
        annual_interest_rate=Decimal("6"),
        loan_term_years=30,
        current_monthly_surplus=Decimal("6000"),
        max_lvr=Decimal("80"),
        minimum_monthly_surplus=Decimal("2000"),
    )
    assert result.additional_loan == Decimal("437000.00")
    assert result.funding_gap == 0
    assert result.lvr == Decimal("87.40")
    assert result.failed_thresholds == ["max_lvr"]
    assert monthly_repayment(Decimal("0"), Decimal("6"), 30) == 0


@pytest.fixture
async def purchase_type(session: AsyncSession) -> LookupItem:
    item = LookupItem(
        category="purchase_type",
        code="HOME_TEST",
        display_name="Home",
        is_active=True,
    )
    session.add(item)
    await session.commit()
    return item


async def test_purchase_plan_with_australian_example_and_feasibility(
    client: AsyncClient, purchase_type: LookupItem
) -> None:
    household = await create_household(client)
    person = (
        await client.post(
            f"/api/v1/households/{household['id']}/people",
            json={"display_name": "Alex", "effective_from": "2020-01-01"},
        )
    ).json()
    response = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans",
        json={
            "display_name": "Possible next home",
            "purchase_type_id": str(purchase_type.id),
            "target_location": {"region": "Example"},
            "intended_use": "LIVE_IN",
            "target_price_min": 400000,
            "target_price_max": 600000,
            "target_date": "2027-01-01",
            "desired_buffer": 10000,
            "max_lvr": 80,
            "minimum_monthly_surplus": 2000,
            "provider_code": "au_purchase",
            "provider_settings": {"transfer_duty_rate": 5},
            "funding_sources": [
                {
                    "display_name": "Savings",
                    "source_type": "SAVINGS",
                    "amount": 100000,
                    "available_date": "2026-01-01",
                },
                {
                    "display_name": "Future gift",
                    "source_type": "GIFT",
                    "amount": 50000,
                    "available_date": "2028-01-01",
                },
            ],
            "costs": [{"code": "legal", "display_name": "Legal advice", "amount": 2000}],
            "ownership": [
                {
                    "owner_type": "PERSON",
                    "person_id": person["id"],
                    "ownership_percentage": 100,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["provider_code"] == "AU_PURCHASE"
    calculation = await client.post(
        f"/api/v1/purchase-plans/{plan['id']}/calculate",
        json={
            "purchase_price": 500000,
            "maximum_additional_borrowing": 450000,
            "annual_interest_rate": 6,
            "loan_term_years": 30,
            "current_monthly_surplus": 6000,
        },
    )
    assert calculation.status_code == 200, calculation.text
    body = calculation.json()
    assert body["required_total"] == "537000.00"
    assert body["available_equity_funding"] == "100000.00"
    assert body["additional_loan_required"] == "437000.00"
    assert body["is_feasible"] is False
    assert body["failed_thresholds"] == ["max_lvr"]
    assert {item["source"] for item in body["costs"]} == {"USER", "AU_PURCHASE"}
    assert any("6% over 30 years" in item for item in body["assumptions_used"])
    assert any("6000 AUD" in item for item in body["assumptions_used"])
    assert any("450000 AUD" in item for item in body["assumptions_used"])
    listed = await client.get(f"/api/v1/households/{household['id']}/purchase-plans")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == plan["id"]


async def test_purchase_plan_rejects_invalid_provider_ownership_and_hidden_access(
    client: AsyncClient, session: AsyncSession, purchase_type: LookupItem
) -> None:
    household = await create_household(client)
    other = Household(display_name="Other", currency="NZD")
    session.add(other)
    await session.flush()
    hidden_person = Person(
        household_id=other.id,
        display_name="Hidden",
        is_active=True,
        effective_from=date(2020, 1, 1),
    )
    session.add(hidden_person)
    await session.commit()
    base = {
        "display_name": "Invalid",
        "purchase_type_id": str(purchase_type.id),
        "intended_use": "PERSONAL",
        "target_price_min": 100,
        "target_price_max": 200,
        "target_date": "2027-01-01",
    }
    missing = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans",
        json=base | {"provider_code": "MISSING"},
    )
    assert missing.status_code == 422
    cross_person = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans",
        json=base
        | {
            "ownership": [
                {
                    "owner_type": "PERSON",
                    "person_id": str(hidden_person.id),
                    "ownership_percentage": 100,
                }
            ]
        },
    )
    assert cross_person.status_code == 422
    hidden_plan = PurchasePlan(
        household_id=other.id,
        display_name="Hidden",
        purchase_type_id=purchase_type.id,
        target_location={},
        intended_use="OTHER",
        target_price_min=Decimal("100"),
        target_price_max=Decimal("200"),
        target_date=date(2027, 1, 1),
        currency="NZD",
        desired_buffer=Decimal("0"),
        provider_settings={},
    )
    session.add(hidden_plan)
    await session.commit()
    hidden = await client.post(
        f"/api/v1/purchase-plans/{hidden_plan.id}/calculate",
        json={
            "purchase_price": 150,
            "maximum_additional_borrowing": 0,
            "annual_interest_rate": 5,
            "loan_term_years": 10,
            "current_monthly_surplus": 0,
        },
    )
    assert hidden.status_code == 404


async def test_purchase_calculation_requires_material_assumptions(
    client: AsyncClient, purchase_type: LookupItem
) -> None:
    household = await create_household(client)
    response = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans",
        json={
            "display_name": "Explicit assumptions",
            "purchase_type_id": str(purchase_type.id),
            "intended_use": "PERSONAL",
            "target_price_min": 100000,
            "target_price_max": 200000,
            "target_date": "2028-01-01",
        },
    )
    assert response.status_code == 201, response.text
    calculation = await client.post(
        f"/api/v1/purchase-plans/{response.json()['id']}/calculate",
        json={"purchase_price": 150000},
    )
    assert calculation.status_code == 422
    missing = {item["loc"][-1] for item in calculation.json()["detail"]}
    assert missing == {
        "maximum_additional_borrowing",
        "annual_interest_rate",
        "loan_term_years",
        "current_monthly_surplus",
    }
