"""Purchase-planning tests."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    Person,
    PurchasePlan,
    PurchasePlanChildRevision,
)
from app.purchases.calculations import calculate_feasibility, monthly_repayment
from tests.households.test_households import create_household


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
            "desired_buffer": 5000,
            "provider_settings": {"transfer_duty_rate": 4},
            "maximum_additional_borrowing": 450000,
            "annual_interest_rate": 6,
            "loan_term_years": 30,
            "current_monthly_surplus": 6000,
        },
    )
    assert calculation.status_code == 200, calculation.text
    body = calculation.json()
    assert body["required_total"] == "527000.00"
    assert body["available_equity_funding"] == "100000.00"
    assert body["additional_loan_required"] == "427000.00"
    assert body["is_feasible"] is False
    assert body["failed_thresholds"] == ["max_lvr"]
    assert {item["source"] for item in body["costs"]} == {"USER", "AU_PURCHASE"}
    assert any("6% over 30 years" in item for item in body["assumptions_used"])
    assert any("6000 AUD" in item for item in body["assumptions_used"])
    assert any("450000 AUD" in item for item in body["assumptions_used"])
    assert any("5000 AUD" in item for item in body["assumptions_used"])
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_price_min", "1e100"),
        ("target_price_max", "100.001"),
        ("desired_buffer", "-1"),
        ("minimum_monthly_surplus", "12345678901234567.89"),
    ],
)
async def test_purchase_plan_rejects_unsafe_money_values(
    client: AsyncClient,
    purchase_type: LookupItem,
    field: str,
    value: str,
) -> None:
    household = await create_household(client)
    payload = {
        "display_name": "Validated plan",
        "purchase_type_id": str(purchase_type.id),
        "intended_use": "PERSONAL",
        "target_price_min": "100.00",
        "target_price_max": "200.00",
        "target_date": "2027-01-01",
        field: value,
    }
    response = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans", json=payload
    )
    assert response.status_code == 422


async def test_purchase_plan_requires_consistent_identified_owners(
    client: AsyncClient, purchase_type: LookupItem
) -> None:
    household = await create_household(client)
    base = {
        "display_name": "Ownership validation",
        "purchase_type_id": str(purchase_type.id),
        "intended_use": "PERSONAL",
        "target_price_min": "100.00",
        "target_price_max": "200.00",
        "target_date": "2027-01-01",
    }
    anonymous = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans",
        json=base | {"ownership": [{"owner_type": "EXTERNAL_PARTY", "ownership_percentage": 100}]},
    )
    inconsistent = await client.post(
        f"/api/v1/households/{household['id']}/purchase-plans",
        json=base
        | {
            "ownership": [
                {
                    "owner_type": "HOUSEHOLD",
                    "external_owner_name": "Not applicable",
                    "ownership_percentage": 100,
                }
            ]
        },
    )
    assert anonymous.status_code == 422
    assert inconsistent.status_code == 422


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


async def test_purchase_plan_detail_children_are_correctable_and_recoverable(
    client: AsyncClient,
    session: AsyncSession,
    purchase_type: LookupItem,
    caplog: pytest.LogCaptureFixture,
) -> None:
    household = await create_household(client)
    person = (
        await client.post(
            f"/api/v1/households/{household['id']}/people",
            json={"display_name": "Detail owner", "effective_from": "2020-01-01"},
        )
    ).json()
    plan = (
        await client.post(
            f"/api/v1/households/{household['id']}/purchase-plans",
            json={
                "display_name": "Audited details",
                "purchase_type_id": str(purchase_type.id),
                "intended_use": "PERSONAL",
                "target_price_min": "500000.00",
                "target_price_max": "600000.00",
                "target_date": "2028-01-01",
            },
        )
    ).json()
    funding = await client.post(
        f"/api/v1/purchase-plans/{plan['id']}/funding-sources",
        json={
            "display_name": "Savings",
            "source_type": "SAVINGS",
            "amount": "100000.00",
            "available_date": "2027-01-01",
            "notes": "private funding note",
        },
    )
    cost = await client.post(
        f"/api/v1/purchase-plans/{plan['id']}/costs",
        json={"code": "LEGAL", "display_name": "Legal fees", "amount": "2500.00"},
    )
    assert funding.status_code == 201
    assert cost.status_code == 201
    funding_body = funding.json()
    corrected = await client.patch(
        f"/api/v1/purchase-plans/{plan['id']}/funding-sources/{funding_body['id']}",
        json={"expected_revision": 1, "amount": "110000.00"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["revision"] == 2
    stale = await client.patch(
        f"/api/v1/purchase-plans/{plan['id']}/funding-sources/{funding_body['id']}",
        json={"expected_revision": 1, "amount": "120000.00"},
    )
    assert stale.status_code == 409
    retired = await client.request(
        "DELETE",
        f"/api/v1/purchase-plans/{plan['id']}/costs/{cost.json()['id']}",
        json={"expected_revision": 1},
    )
    assert retired.status_code == 204
    ownership = await client.put(
        f"/api/v1/purchase-plans/{plan['id']}/ownership",
        json={
            "expected_revision_ids": [],
            "ownership": [
                {
                    "owner_type": "PERSON",
                    "person_id": person["id"],
                    "ownership_percentage": "65.0000",
                },
                {
                    "owner_type": "EXTERNAL_PARTY",
                    "external_owner_name": "Family member",
                    "ownership_percentage": "35.0000",
                },
            ],
        },
    )
    assert ownership.status_code == 200
    detail = await client.get(f"/api/v1/purchase-plans/{plan['id']}")
    assert detail.status_code == 200
    assert detail.json()["funding_sources"][0]["amount"] == "110000.00"
    assert detail.json()["costs"] == []
    assert len(detail.json()["ownership"]) == 2
    revisions = list(
        await session.scalars(
            select(PurchasePlanChildRevision).where(
                PurchasePlanChildRevision.purchase_plan_id == uuid.UUID(plan["id"])
            )
        )
    )
    assert [item.action for item in revisions] == [
        "CREATED",
        "CREATED",
        "CORRECTED",
        "RETIRED",
        "REPLACED",
    ]
    assert revisions[2].previous_state["amount"] == "100000.00"
    assert revisions[2].previous_state["notes"] == "private funding note"
    assert "private funding note" not in caplog.text
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(household["id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()
    assert (await client.get(f"/api/v1/purchase-plans/{plan['id']}")).status_code == 200
    denied = await client.post(
        f"/api/v1/purchase-plans/{plan['id']}/costs",
        json={"code": "DENIED", "display_name": "Denied", "amount": "1.00"},
    )
    assert denied.status_code == 403


async def test_purchase_child_corrections_reject_null_and_noop_payloads(
    client: AsyncClient,
    session: AsyncSession,
    purchase_type: LookupItem,
    caplog: pytest.LogCaptureFixture,
) -> None:
    household = await create_household(client)
    plan = (
        await client.post(
            f"/api/v1/households/{household['id']}/purchase-plans",
            json={
                "display_name": "Correction validation",
                "purchase_type_id": str(purchase_type.id),
                "intended_use": "PERSONAL",
                "target_price_min": "400000.00",
                "target_price_max": "500000.00",
                "target_date": "2028-01-01",
            },
        )
    ).json()
    funding = (
        await client.post(
            f"/api/v1/purchase-plans/{plan['id']}/funding-sources",
            json={
                "display_name": "Savings",
                "source_type": "SAVINGS",
                "amount": "75000.00",
                "available_date": "2027-01-01",
                "is_borrowed": False,
                "notes": "clearable note",
            },
        )
    ).json()
    cost = (
        await client.post(
            f"/api/v1/purchase-plans/{plan['id']}/costs",
            json={
                "code": "LEGAL",
                "display_name": "Legal fees",
                "amount": "2500.00",
                "is_estimate": True,
            },
        )
    ).json()
    funding_url = f"/api/v1/purchase-plans/{plan['id']}/funding-sources/{funding['id']}"
    cost_url = f"/api/v1/purchase-plans/{plan['id']}/costs/{cost['id']}"

    for field in (
        "display_name",
        "source_type",
        "amount",
        "available_date",
        "is_borrowed",
    ):
        response = await client.patch(funding_url, json={"expected_revision": 1, field: None})
        assert response.status_code == 422, field
    for field in ("code", "display_name", "amount", "is_estimate"):
        response = await client.patch(cost_url, json={"expected_revision": 1, field: None})
        assert response.status_code == 422, field

    assert (await client.patch(funding_url, json={"expected_revision": 1})).status_code == 422
    assert (await client.patch(cost_url, json={"expected_revision": 1})).status_code == 422
    assert (
        await client.patch(funding_url, json={"expected_revision": 1, "amount": "75000.00"})
    ).status_code == 422
    assert (
        await client.patch(cost_url, json={"expected_revision": 1, "display_name": "Legal fees"})
    ).status_code == 422

    cleared = await client.patch(funding_url, json={"expected_revision": 1, "notes": None})
    corrected_cost = await client.patch(
        cost_url, json={"expected_revision": 1, "amount": "2600.00"}
    )
    assert cleared.status_code == 200
    assert cleared.json()["notes"] is None
    assert cleared.json()["revision"] == 2
    assert corrected_cost.status_code == 200
    assert corrected_cost.json()["revision"] == 2

    retired_funding = await client.request("DELETE", funding_url, json={"expected_revision": 2})
    retired_cost = await client.request("DELETE", cost_url, json={"expected_revision": 2})
    assert retired_funding.status_code == 204
    assert retired_cost.status_code == 204

    revisions = list(
        await session.scalars(
            select(PurchasePlanChildRevision).where(
                PurchasePlanChildRevision.purchase_plan_id == uuid.UUID(plan["id"])
            )
        )
    )
    assert [item.action for item in revisions] == [
        "CREATED",
        "CREATED",
        "CORRECTED",
        "CORRECTED",
        "RETIRED",
        "RETIRED",
    ]
    for event in (
        "purchase_funding_source_retired",
        "purchase_cost_corrected",
        "purchase_cost_retired",
    ):
        assert event in caplog.text
    assert household["id"] in caplog.text
    assert plan["id"] in caplog.text
    assert funding["id"] in caplog.text
    assert cost["id"] in caplog.text
    assert "clearable note" not in caplog.text


async def test_purchase_ownership_replacement_rejects_stale_and_cross_household_people(
    client: AsyncClient,
    session: AsyncSession,
    purchase_type: LookupItem,
) -> None:
    household = await create_household(client)
    other = Household(display_name="Other ownership", currency="AUD")
    session.add(other)
    await session.flush()
    outsider = Person(
        household_id=other.id,
        display_name="Outsider",
        is_active=True,
        effective_from=date(2020, 1, 1),
    )
    session.add(outsider)
    await session.commit()
    plan = (
        await client.post(
            f"/api/v1/households/{household['id']}/purchase-plans",
            json={
                "display_name": "Ownership checks",
                "purchase_type_id": str(purchase_type.id),
                "intended_use": "PERSONAL",
                "target_price_min": "1.00",
                "target_price_max": "2.00",
                "target_date": "2028-01-01",
            },
        )
    ).json()
    cross_household = await client.put(
        f"/api/v1/purchase-plans/{plan['id']}/ownership",
        json={
            "expected_revision_ids": [],
            "ownership": [
                {
                    "owner_type": "PERSON",
                    "person_id": str(outsider.id),
                    "ownership_percentage": 100,
                }
            ],
        },
    )
    assert cross_household.status_code == 422
    created = await client.put(
        f"/api/v1/purchase-plans/{plan['id']}/ownership",
        json={
            "expected_revision_ids": [],
            "ownership": [{"owner_type": "HOUSEHOLD", "ownership_percentage": 100}],
        },
    )
    assert created.status_code == 200
    stale = await client.put(
        f"/api/v1/purchase-plans/{plan['id']}/ownership",
        json={
            "expected_revision_ids": [],
            "ownership": [{"owner_type": "HOUSEHOLD", "ownership_percentage": 100}],
        },
    )
    assert stale.status_code == 409
