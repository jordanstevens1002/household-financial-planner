import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.loan_calculations import minimum_repayment
from app.models import (
    EventType,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    Property,
    RepaymentFrequency,
)
from tests.test_households import create_household


@pytest.fixture
async def loan_setup(client: AsyncClient, session: AsyncSession) -> dict[str, str]:
    household = await create_household(client)
    property_type = LookupItem(
        category="property_type", code="LOAN_TEST", display_name="Loan test", is_active=True
    )
    status = LookupItem(
        category="property_status",
        code="LOAN_ACTIVE",
        display_name="Active",
        is_active=True,
        is_active_asset=True,
    )
    loan_type = LookupItem(
        category="loan_type", code="TEST_MORTGAGE", display_name="Mortgage", is_active=True
    )
    goal_type = LookupItem(
        category="goal_type",
        code="MAXIMUM_WEEKLY_REPAYMENT",
        display_name="Maximum weekly repayment",
        is_active=True,
    )
    event_codes = [
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
    ]
    event_types = [
        EventType(code=code, display_name=code, priority=index + 1)
        for index, code in enumerate(event_codes)
    ]
    session.add_all([property_type, status, loan_type, goal_type, *event_types])
    await session.flush()
    property_record = Property(
        household_id=uuid.UUID(household["id"]),
        display_name="Secured property",
        property_type_id=property_type.id,
        current_status_id=status.id,
        default_currency="AUD",
    )
    session.add(property_record)
    await session.commit()
    return {
        "household_id": household["id"],
        "property_id": str(property_record.id),
        "loan_type_id": str(loan_type.id),
        "goal_type_id": str(goal_type.id),
        **{item.code: str(item.id) for item in event_types},
    }


def loan_payload(
    setup: dict[str, str],
    *,
    display_name: str = "Historical mortgage",
    frequency: str = "MONTHLY",
    property_id: str | None = "default",
) -> dict[str, object]:
    resolved_property = setup["property_id"] if property_id == "default" else property_id
    return {
        "property_id": resolved_property,
        "display_name": display_name,
        "loan_type_id": setup["loan_type_id"],
        "opening_balance": "500000.00",
        "opening_balance_date": "2020-01-01",
        "initial_interest_rate": "6.0000",
        "scheduled_repayment": "3000.00",
        "term_months": 360,
        "interest_calculation_method": "MONTHLY",
        "repayment_frequency": frequency,
        "is_interest_only": False,
    }


async def create_loan(
    client: AsyncClient, setup: dict[str, str], **overrides: object
) -> dict[str, object]:
    payload = loan_payload(setup) | overrides
    response = await client.post(f"/api/v1/households/{setup['household_id']}/loans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def add_loan_event(
    client: AsyncClient,
    setup: dict[str, str],
    loan_id: str,
    code: str,
    *,
    amount: int | None = None,
    percentage: int | None = None,
    payload: dict[str, object] | None = None,
    effective_at: str = "2020-01-15T00:00:00+00:00",
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/loans/{loan_id}/events",
        json={
            "event_type_id": setup[code],
            "effective_at": effective_at,
            "amount": amount,
            "percentage": percentage,
            "payload": payload or {},
            "classification": "OBSERVED",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_historical_personal_loan_and_multiple_property_loans(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    group = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Mortgage splits", "property_id": loan_setup["property_id"]},
    )
    assert group.status_code == 201
    first = await create_loan(client, loan_setup, loan_group_id=group.json()["id"])
    second = await create_loan(
        client, loan_setup, display_name="Split loan", loan_group_id=group.json()["id"]
    )
    personal = await create_loan(
        client, loan_setup, display_name="Personal loan", property_id=None, currency="NZD"
    )
    response = await client.get(f"/api/v1/households/{loan_setup['household_id']}/loans")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {
        first["id"],
        second["id"],
        personal["id"],
    }
    assert first["opening_balance_date"] == "2020-01-01"
    assert first["currency"] == "AUD"
    assert personal["property_id"] is None
    assert personal["currency"] == "NZD"


async def test_schedule_applies_offsets_rate_changes_lump_sums_and_redraw(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup)
    loan_id = str(loan["id"])
    await add_loan_event(client, loan_setup, loan_id, "LOAN_OFFSET_CHANGED", amount=100000)
    await add_loan_event(
        client,
        loan_setup,
        loan_id,
        "LOAN_RATE_CHANGED",
        percentage=5,
        effective_at="2020-02-15T00:00:00+00:00",
    )
    await add_loan_event(
        client,
        loan_setup,
        loan_id,
        "LOAN_LUMP_SUM_PAID",
        amount=10000,
        effective_at="2020-03-15T00:00:00+00:00",
    )
    await add_loan_event(
        client,
        loan_setup,
        loan_id,
        "LOAN_REDRAWN",
        amount=2000,
        effective_at="2020-04-15T00:00:00+00:00",
    )
    response = await client.get(
        f"/api/v1/loans/{loan_id}/schedule", params={"through_date": "2020-05-01"}
    )
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert entries[0]["interest"] == "2000.00"
    assert entries[1]["annual_interest_rate"] == "5.0000"
    assert entries[-1]["closing_balance"] < entries[0]["closing_balance"]
    assert Decimal(response.json()["interest_saved_vs_no_offset"]) > 0


async def test_full_amortisation_daily_interest_and_interest_only(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    amortising = await create_loan(client, loan_setup, scheduled_repayment=None)
    full = await client.get(f"/api/v1/loans/{amortising['id']}/schedule")
    assert full.status_code == 200
    assert full.json()["remaining_balance"] == "0.00"
    assert full.json()["payoff_date"] is not None
    daily = await create_loan(
        client,
        loan_setup,
        display_name="Daily interest",
        interest_calculation_method="DAILY",
        is_interest_only=True,
    )
    await add_loan_event(
        client,
        loan_setup,
        str(daily["id"]),
        "LOAN_OFFSET_CHANGED",
        amount=100000,
    )
    partial = await client.get(
        f"/api/v1/loans/{daily['id']}/schedule", params={"through_date": "2020-02-01"}
    )
    assert "DAILY_INTEREST_USES_ACTUAL_365_BASIS" in partial.json()["data_quality_flags"]
    first = partial.json()["entries"][0]
    assert first["interest"] == "2268.49"
    assert first["repayment"] == first["interest"]
    assert first["principal"] == "0.00"


async def test_schedule_does_not_assume_a_term_for_open_ended_loans(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup, term_months=None)
    undated = await client.get(f"/api/v1/loans/{loan['id']}/schedule")
    assert undated.status_code == 422
    assert (
        undated.json()["detail"] == "A loan term or through_date is required to generate a schedule"
    )

    dated = await client.get(
        f"/api/v1/loans/{loan['id']}/schedule", params={"through_date": "2020-04-01"}
    )
    assert dated.status_code == 200, dated.text
    assert len(dated.json()["entries"]) == 3


async def test_repayment_term_interest_only_and_closure_events(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup, is_interest_only=True)
    loan_id = str(loan["id"])
    await add_loan_event(client, loan_setup, loan_id, "LOAN_INTEREST_ONLY_ENDED")
    await add_loan_event(client, loan_setup, loan_id, "LOAN_REPAYMENT_CHANGED", amount=4000)
    await add_loan_event(
        client,
        loan_setup,
        loan_id,
        "LOAN_TERM_CHANGED",
        payload={"term_months": 120},
    )
    await add_loan_event(
        client,
        loan_setup,
        loan_id,
        "LOAN_INTEREST_ONLY_STARTED",
        effective_at="2020-03-15T00:00:00+00:00",
    )
    await add_loan_event(
        client,
        loan_setup,
        loan_id,
        "LOAN_CLOSED",
        effective_at="2020-06-15T00:00:00+00:00",
    )
    schedule = await client.get(f"/api/v1/loans/{loan_id}/schedule")
    entries = schedule.json()["entries"]
    assert entries[0]["repayment"] == "4000.00"
    assert Decimal(entries[0]["principal"]) > 0
    assert entries[2]["principal"] == "0.00"
    assert schedule.json()["payoff_date"] == "2020-06-15"


@pytest.mark.parametrize(
    ("frequency", "expected_date"),
    [("WEEKLY", "2020-01-08"), ("FORTNIGHTLY", "2020-01-15"), ("MONTHLY", "2020-02-01")],
)
async def test_repayment_frequencies(
    client: AsyncClient,
    loan_setup: dict[str, str],
    frequency: str,
    expected_date: str,
) -> None:
    loan = await create_loan(client, loan_setup, repayment_frequency=frequency)
    schedule = await client.get(
        f"/api/v1/loans/{loan['id']}/schedule", params={"through_date": "2020-02-01"}
    )
    assert schedule.json()["entries"][0]["payment_date"] == expected_date


async def test_refinancing_is_atomic_and_closes_old_schedule(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    old = await create_loan(client, loan_setup)
    replacement = loan_payload(loan_setup, display_name="Replacement loan") | {
        "opening_balance": "480000.00",
        "opening_balance_date": "2022-01-01",
        "initial_interest_rate": "4.5000",
    }
    response = await client.post(
        f"/api/v1/loans/{old['id']}/refinance",
        json={
            "effective_at": "2022-01-01T00:00:00+00:00",
            "replacement_loan": replacement,
            "idempotency_key": "refinance-2022",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["closed_loan_id"] == old["id"]
    assert body["replacement_loan"]["opening_balance"] == "480000.00"
    assert body["refinance_event"]["loan_id"] == old["id"]
    schedule = await client.get(f"/api/v1/loans/{old['id']}/schedule")
    assert schedule.json()["payoff_date"] == "2022-01-01"
    old_read = await client.get(f"/api/v1/loans/{old['id']}")
    assert old_read.json()["is_active"] is False


async def test_configurable_weekly_repayment_target(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup)
    goal = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/goals",
        json={
            "loan_id": loan["id"],
            "goal_type_id": loan_setup["goal_type_id"],
            "display_name": "Comfortable weekly payment",
            "target_amount": "700.00",
            "priority": 1,
        },
    )
    assert goal.status_code == 201
    result = await client.post(
        f"/api/v1/loans/{loan['id']}/target-calculation",
        json={"goal_id": goal.json()["id"], "as_of": "2020-01-01"},
    )
    assert result.status_code == 200
    assert result.json()["target_amount"] == "700.00"
    assert Decimal(result.json()["required_repayment"]) > 0
    assert result.json()["within_target"] is True
    listed = await client.get(f"/api/v1/households/{loan_setup['household_id']}/goals")
    assert [item["id"] for item in listed.json()] == [goal.json()["id"]]


async def test_cross_household_property_is_rejected_and_viewer_cannot_write(
    client: AsyncClient, session: AsyncSession, loan_setup: dict[str, str]
) -> None:
    other = Household(display_name="Other", currency="EUR")
    session.add(other)
    await session.flush()
    hidden_property = Property(
        household_id=other.id,
        display_name="Other property",
        property_type_id=uuid.uuid4(),
        current_status_id=uuid.uuid4(),
        default_currency="EUR",
    )
    session.add(hidden_property)
    await session.commit()
    invalid = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loans",
        json=loan_payload(loan_setup) | {"property_id": str(hidden_property.id)},
    )
    assert invalid.status_code == 422
    loan = await create_loan(client, loan_setup)
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(loan_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()
    blocked = await client.post(
        f"/api/v1/loans/{loan['id']}/events",
        json={
            "event_type_id": loan_setup["LOAN_RATE_CHANGED"],
            "effective_at": datetime.now(UTC).isoformat(),
            "percentage": 4,
            "classification": "PLANNED",
        },
    )
    assert blocked.status_code == 403


def test_minimum_repayment_is_frequency_aware() -> None:
    balance = minimum_repayment(
        balance=500000,
        annual_rate=6,
        periods=360,
        frequency=RepaymentFrequency.MONTHLY,
    )
    weekly = minimum_repayment(
        balance=500000,
        annual_rate=6,
        periods=30 * 52,
        frequency=RepaymentFrequency.WEEKLY,
    )
    assert balance > weekly
