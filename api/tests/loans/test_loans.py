"""Loan tests."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.loans.calculations import minimum_repayment
from app.models import (
    EventType,
    Household,
    HouseholdMembership,
    HouseholdRole,
    Loan,
    LoanGroup,
    LookupItem,
    Property,
    RepaymentFrequency,
)
from tests.households.test_households import create_household


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
        "status_id": str(status.id),
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


async def test_loan_can_be_corrected_and_closed_with_audit(
    client: AsyncClient,
    loan_setup: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.loans.router.logger.info",
        lambda event, **values: audit_events.append((event, values)),
    )
    loan = await create_loan(client, loan_setup)

    corrected = await client.patch(
        f"/api/v1/loans/{loan['id']}",
        json={
            "account_reference_masked": "****6789",
            "scheduled_repayment": "3250.00",
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["scheduled_repayment"] == "3250.00"
    assert corrected.json()["account_reference_masked"] == "****6789"
    assert audit_events[-1][0] == "loan_corrected"
    assert audit_events[-1][1]["before"]["scheduled_repayment"] == "3000.00"
    assert audit_events[-1][1]["after"]["scheduled_repayment"] == "3250.00"

    cannot_clear_required = await client.patch(
        f"/api/v1/loans/{loan['id']}", json={"opening_balance": None}
    )
    assert cannot_clear_required.status_code == 422

    closed = await client.post(
        f"/api/v1/loans/{loan['id']}/close",
        json={"effective_date": "2020-04-15"},
    )
    assert closed.status_code == 200
    assert closed.json()["is_active"] is False
    assert audit_events[-1][0] == "loan_closed"
    assert audit_events[-1][1]["effective_date"] == "2020-04-15"

    before_closure = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2020-03-01"},
    )
    assert before_closure.json()["annual_loan_repayments"] == "39000.00"
    after_closure = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2020-05-01"},
    )
    assert after_closure.json()["annual_loan_repayments"] == "0.00"


async def test_loan_account_reference_must_be_explicitly_masked(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    exposed = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loans",
        json=loan_payload(loan_setup) | {"account_reference_masked": "123456789"},
    )
    assert exposed.status_code == 422

    masked = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loans",
        json=loan_payload(loan_setup) | {"account_reference_masked": "•••• 6789"},
    )
    assert masked.status_code == 201
    assert masked.json()["account_reference_masked"] == "•••• 6789"


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


async def test_loan_groups_are_listed_and_can_be_corrected(
    client: AsyncClient,
    loan_setup: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = await client.get(f"/api/v1/households/{loan_setup['household_id']}/loan-groups")
    assert empty.status_code == 200
    assert empty.json() == []

    audit_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.loans.router.logger.info",
        lambda event, **values: audit_events.append((event, values)),
    )
    later = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Variable splits", "property_id": loan_setup["property_id"]},
    )
    earlier = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Fixed splits", "property_id": loan_setup["property_id"]},
    )
    assert later.status_code == earlier.status_code == 201

    listed = await client.get(f"/api/v1/households/{loan_setup['household_id']}/loan-groups")
    assert [item["display_name"] for item in listed.json()] == [
        "Fixed splits",
        "Variable splits",
    ]

    grouped = await create_loan(client, loan_setup, loan_group_id=earlier.json()["id"])
    ungrouped = await create_loan(client, loan_setup, display_name="Ungrouped split")
    assert grouped["loan_group_id"] == earlier.json()["id"]
    assert ungrouped["loan_group_id"] is None

    moved = await client.patch(
        f"/api/v1/loans/{ungrouped['id']}",
        json={"loan_group_id": later.json()["id"]},
    )
    assert moved.status_code == 200
    assert moved.json()["loan_group_id"] == later.json()["id"]
    assert audit_events[-1][0] == "loan_corrected"
    assert audit_events[-1][1]["before"]["loan_group_id"] is None
    assert audit_events[-1][1]["after"]["loan_group_id"] == later.json()["id"]

    cleared = await client.patch(f"/api/v1/loans/{ungrouped['id']}", json={"loan_group_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["loan_group_id"] is None

    renamed = await client.patch(
        f"/api/v1/loan-groups/{later.json()['id']}",
        json={"display_name": "  Flexible   splits  "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Flexible splits"
    assert audit_events[-1][0] == "loan_group_renamed"
    assert audit_events[-1][1]["previous_name"] == "Variable splits"

    duplicate = await client.patch(
        f"/api/v1/loan-groups/{later.json()['id']}",
        json={"display_name": "fixed SPLITS"},
    )
    assert duplicate.status_code == 409
    empty_name = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "   ", "property_id": loan_setup["property_id"]},
    )
    assert empty_name.status_code == 422

    assigned_removal = await client.delete(f"/api/v1/loan-groups/{earlier.json()['id']}")
    assert assigned_removal.status_code == 409
    confirmed_removal = await client.post(
        f"/api/v1/loan-groups/{earlier.json()['id']}/remove",
        json={"assigned_loan_ids": [grouped["id"]]},
    )
    assert confirmed_removal.status_code == 204
    assert (await client.get(f"/api/v1/households/{loan_setup['household_id']}/loans")).json()[0][
        "loan_group_id"
    ] is None
    assert audit_events[-1][0] == "loan_group_removed"
    assert audit_events[-1][1]["affected_loans"] == [
        {"id": grouped["id"], "display_name": grouped["display_name"]}
    ]
    removed = await client.delete(f"/api/v1/loan-groups/{later.json()['id']}")
    assert removed.status_code == 204
    assert audit_events[-1][0] == "loan_group_removed"
    assert audit_events[-1][1]["removed_group"]["display_name"] == "Flexible splits"


async def test_only_household_administrators_can_remove_populated_groups(
    client: AsyncClient,
    session: AsyncSession,
    loan_setup: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Package", "property_id": loan_setup["property_id"]},
    )
    first = await create_loan(client, loan_setup, loan_group_id=group.json()["id"])
    second = await create_loan(
        client,
        loan_setup,
        display_name="Offset split",
        loan_group_id=group.json()["id"],
    )
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(loan_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.EDITOR
    await session.commit()

    endpoint = f"/api/v1/loan-groups/{group.json()['id']}/remove"
    confirmation = {"assigned_loan_ids": [first["id"], second["id"]]}
    forbidden = await client.post(endpoint, json=confirmation)
    assert forbidden.status_code == 403
    unchanged = await client.get(f"/api/v1/households/{loan_setup['household_id']}/loans")
    assert {item["loan_group_id"] for item in unchanged.json()} == {group.json()["id"]}

    membership.role = HouseholdRole.ADMIN
    await session.commit()
    confirmation_required = await client.delete(f"/api/v1/loan-groups/{group.json()['id']}")
    assert confirmation_required.status_code == 409
    stale_confirmation = await client.post(
        endpoint,
        json={"assigned_loan_ids": [first["id"]]},
    )
    assert stale_confirmation.status_code == 409

    audit_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.loans.router.logger.info",
        lambda event, **values: audit_events.append((event, values)),
    )
    removed = await client.post(endpoint, json=confirmation)
    assert removed.status_code == 204
    resulting = await client.get(f"/api/v1/households/{loan_setup['household_id']}/loans")
    assert {item["loan_group_id"] for item in resulting.json()} == {None}
    assert audit_events == [
        (
            "loan_group_removed",
            {
                "actor_user_id": audit_events[0][1]["actor_user_id"],
                "household_id": loan_setup["household_id"],
                "property_id": loan_setup["property_id"],
                "loan_group_id": group.json()["id"],
                "removed_group": group.json(),
                "affected_loans": [
                    {"id": first["id"], "display_name": first["display_name"]},
                    {"id": second["id"], "display_name": second["display_name"]},
                ],
            },
        )
    ]


async def test_populated_group_removal_uses_a_bounded_body_for_many_loans(
    client: AsyncClient, session: AsyncSession, loan_setup: dict[str, str]
) -> None:
    group = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Many splits", "property_id": loan_setup["property_id"]},
    )
    seed = await create_loan(client, loan_setup, loan_group_id=group.json()["id"])
    seed_record = await session.get(Loan, uuid.UUID(seed["id"]))
    assert seed_record is not None
    additional = [
        Loan(
            household_id=seed_record.household_id,
            property_id=seed_record.property_id,
            loan_group_id=seed_record.loan_group_id,
            display_name=f"Split {index:03d}",
            lender=None,
            account_reference_masked=None,
            loan_type_id=seed_record.loan_type_id,
            currency=seed_record.currency,
            original_balance=None,
            opening_balance=seed_record.opening_balance,
            opening_balance_date=seed_record.opening_balance_date,
            initial_interest_rate=seed_record.initial_interest_rate,
            scheduled_repayment=seed_record.scheduled_repayment,
            term_months=seed_record.term_months,
            interest_calculation_method=seed_record.interest_calculation_method,
            repayment_frequency=seed_record.repayment_frequency,
            is_interest_only=False,
            is_active=True,
            notes=None,
        )
        for index in range(149)
    ]
    session.add_all(additional)
    await session.commit()
    expected_ids = [seed["id"], *(str(loan.id) for loan in additional)]

    removed = await client.post(
        f"/api/v1/loan-groups/{group.json()['id']}/remove",
        json={"assigned_loan_ids": expected_ids},
    )
    assert removed.status_code == 204
    resulting = await client.get(f"/api/v1/households/{loan_setup['household_id']}/loans")
    assert len(resulting.json()) == 150
    assert {loan["loan_group_id"] for loan in resulting.json()} == {None}


async def test_loan_group_assignment_requires_the_same_property_and_household(
    client: AsyncClient, session: AsyncSession, loan_setup: dict[str, str]
) -> None:
    other_property = Property(
        household_id=uuid.UUID(loan_setup["household_id"]),
        display_name="Second secured property",
        property_type_id=uuid.uuid4(),
        current_status_id=uuid.uuid4(),
        default_currency="AUD",
    )
    other_household = Household(display_name="Other household", currency="NZD")
    session.add_all([other_property, other_household])
    await session.flush()
    wrong_property_group = LoanGroup(
        household_id=uuid.UUID(loan_setup["household_id"]),
        property_id=other_property.id,
        display_name="Other property splits",
    )
    wrong_household_group = LoanGroup(
        household_id=other_household.id,
        property_id=None,
        display_name="Hidden splits",
    )
    session.add_all([wrong_property_group, wrong_household_group])
    await session.commit()

    for group_id in (wrong_property_group.id, wrong_household_group.id):
        rejected = await client.post(
            f"/api/v1/households/{loan_setup['household_id']}/loans",
            json=loan_payload(loan_setup) | {"loan_group_id": str(group_id)},
        )
        assert rejected.status_code == 422

    loan = await create_loan(client, loan_setup)
    rejected_correction = await client.patch(
        f"/api/v1/loans/{loan['id']}",
        json={"loan_group_id": str(wrong_property_group.id)},
    )
    assert rejected_correction.status_code == 422


async def test_property_debt_reconciliation_is_dated_and_preserves_closed_history(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    endpoint = f"/api/v1/properties/{loan_setup['property_id']}/loan-debt-reconciliation"
    empty = await client.get(endpoint, params={"as_of": "2020-01-01"})
    assert empty.status_code == 200
    assert empty.json()["status"] == "NO_LINKED_LOANS"
    assert empty.json()["recorded_property_debt"] is None
    assert empty.json()["linked_loan_balance"] == "0.00"

    first = await create_loan(client, loan_setup, opening_balance="300000.00")
    second = await create_loan(
        client,
        loan_setup,
        display_name="Second split",
        opening_balance="200000.00",
    )
    missing = await client.get(endpoint, params={"as_of": "2020-01-01"})
    assert missing.json()["status"] == "RECORDED_DEBT_MISSING"
    assert missing.json()["linked_loan_balance"] == "500000.00"
    assert {item["loan_id"] for item in missing.json()["loans"]} == {
        first["id"],
        second["id"],
    }

    for baseline_date, debt in (
        ("2020-01-01", "500000.00"),
        ("2020-01-10", "450000.00"),
        ("2020-01-20", "200000.00"),
    ):
        created = await client.post(
            f"/api/v1/properties/{loan_setup['property_id']}/baselines",
            json={
                "baseline_date": baseline_date,
                "property_value": "800000.00",
                "loan_balance_total": debt,
                "status_id": loan_setup["status_id"],
            },
        )
        assert created.status_code == 201, created.text

    matched = await client.get(endpoint, params={"as_of": "2020-01-01"})
    assert matched.json()["status"] == "MATCHED"
    assert matched.json()["difference"] == "0.00"
    mismatch = await client.get(endpoint, params={"as_of": "2020-01-10"})
    assert mismatch.json()["status"] == "MISMATCH"
    assert mismatch.json()["difference"] == "50000.00"

    closed = await client.post(
        f"/api/v1/loans/{first['id']}/close",
        json={"effective_date": "2020-01-15"},
    )
    assert closed.status_code == 200
    historical = await client.get(endpoint, params={"as_of": "2020-01-10"})
    assert historical.json()["linked_loan_balance"] == "500000.00"
    after_close = await client.get(endpoint, params={"as_of": "2020-01-20"})
    assert after_close.json()["status"] == "MATCHED"
    assert after_close.json()["linked_loan_balance"] == "200000.00"
    assert [item["loan_id"] for item in after_close.json()["loans"]] == [second["id"]]


async def test_property_debt_reconciliation_refuses_incompatible_currencies(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    await create_loan(client, loan_setup, currency="NZD")
    response = await client.get(
        f"/api/v1/properties/{loan_setup['property_id']}/loan-debt-reconciliation",
        params={"as_of": "2020-01-01"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CURRENCY_MISMATCH"
    assert response.json()["linked_loan_balance"] is None
    assert response.json()["difference"] is None


async def test_property_debt_reconciliation_preserves_household_isolation(
    client: AsyncClient, session: AsyncSession, loan_setup: dict[str, str]
) -> None:
    hidden_household = Household(display_name="Hidden", currency="AUD", jurisdiction="AU")
    session.add(hidden_household)
    await session.flush()
    visible_property = await session.get(Property, uuid.UUID(loan_setup["property_id"]))
    assert visible_property is not None
    hidden_property = Property(
        household_id=hidden_household.id,
        display_name="Hidden property",
        property_type_id=visible_property.property_type_id,
        current_status_id=visible_property.current_status_id,
        default_currency="AUD",
    )
    session.add(hidden_property)
    await session.commit()

    response = await client.get(
        f"/api/v1/properties/{hidden_property.id}/loan-debt-reconciliation",
        params={"as_of": "2020-01-01"},
    )
    assert response.status_code == 404


async def test_property_debt_reconciliation_reports_unprojectable_open_ended_loan(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(
        client,
        loan_setup,
        display_name="Repayment not recorded",
        scheduled_repayment=None,
        term_months=None,
    )
    response = await client.get(
        f"/api/v1/properties/{loan_setup['property_id']}/loan-debt-reconciliation",
        params={"as_of": "2020-02-01"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UNPROJECTABLE_LOANS"
    assert response.json()["linked_loan_balance"] is None
    assert response.json()["loans"] == [
        {
            "loan_id": loan["id"],
            "display_name": "Repayment not recorded",
            "currency": "AUD",
            "effective_balance": None,
            "data_quality_flags": ["LOAN_BALANCE_CANNOT_BE_PROJECTED"],
        }
    ]


async def test_property_debt_reconciliation_bounds_horizon_and_handles_many_loans(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    endpoint = f"/api/v1/properties/{loan_setup['property_id']}/loan-debt-reconciliation"
    distant = await client.get(endpoint, params={"as_of": "9999-12-31"})
    assert distant.status_code == 422
    assert "100 years" in distant.json()["detail"]

    for index in range(12):
        await create_loan(
            client,
            loan_setup,
            display_name=f"Loan {index + 1}",
            frequency="WEEKLY",
            opening_balance="100.00",
            initial_interest_rate="0.0000",
            scheduled_repayment="10.00",
            term_months=None,
        )
    response = await client.get(endpoint, params={"as_of": "2020-01-15"})
    assert response.status_code == 200
    assert response.json()["status"] == "RECORDED_DEBT_MISSING"
    assert len(response.json()["loans"]) == 12


async def test_schedule_resumes_repayments_after_payoff_and_redraw(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(
        client,
        loan_setup,
        opening_balance="10000.00",
        initial_interest_rate="0.0000",
        scheduled_repayment="10000.00",
        term_months=12,
    )
    await add_loan_event(
        client,
        loan_setup,
        str(loan["id"]),
        "LOAN_REDRAWN",
        amount=5000,
        effective_at="2020-02-15T00:00:00+00:00",
    )
    schedule = await client.get(
        f"/api/v1/loans/{loan['id']}/schedule",
        params={"through_date": "2020-03-01"},
    )
    assert schedule.status_code == 200
    assert schedule.json()["remaining_balance"] == "0.00"
    assert schedule.json()["entries"][-1]["opening_balance"] == "5000.00"


async def test_loan_repayments_flow_into_cashflow_and_follow_dated_events(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup)
    household_id = loan_setup["household_id"]
    initial = await client.get(
        f"/api/v1/households/{household_id}/cashflow",
        params={"as_of": "2020-02-01"},
    )
    assert initial.status_code == 200
    assert initial.json()["annual_ordinary_expenses"] == "0.00"
    assert initial.json()["annual_loan_repayments"] == "36000.00"
    assert initial.json()["annual_expenses"] == "36000.00"
    assert initial.json()["monthly_loan_repayments"] == "3000.00"
    assert initial.json()["monthly_surplus"] == "-3000.00"
    assert initial.json()["loan_repayments"][0]["periodic_repayment"] == "3000.00"

    await add_loan_event(
        client,
        loan_setup,
        str(loan["id"]),
        "LOAN_REPAYMENT_CHANGED",
        amount=3500,
        effective_at="2020-02-15T00:00:00+00:00",
    )
    changed = await client.get(
        f"/api/v1/households/{household_id}/cashflow",
        params={"as_of": "2020-03-01"},
    )
    assert changed.json()["annual_loan_repayments"] == "42000.00"

    await add_loan_event(
        client,
        loan_setup,
        str(loan["id"]),
        "LOAN_CLOSED",
        effective_at="2020-04-15T00:00:00+00:00",
    )
    closed = await client.get(
        f"/api/v1/households/{household_id}/cashflow",
        params={"as_of": "2020-05-01"},
    )
    assert closed.json()["annual_loan_repayments"] == "0.00"
    assert closed.json()["loan_repayments"] == []


async def test_advanced_repayment_responsibility_is_optional_dated_attribution(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup)
    first_person = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/people",
        json={"display_name": "First payer", "effective_from": "2020-01-01"},
    )
    second_person = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/people",
        json={"display_name": "Second payer", "effective_from": "2020-01-01"},
    )
    assert first_person.status_code == second_person.status_code == 201
    first = await client.post(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
        json={
            "person_id": first_person.json()["id"],
            "responsibility_percentage": 70,
            "effective_from": "2020-01-01",
        },
    )
    second = await client.post(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
        json={
            "person_id": second_person.json()["id"],
            "responsibility_percentage": 30,
            "effective_from": "2020-01-01",
        },
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["warnings"]
    assert second.json()["total_percentage"] == "100.00"
    listed = await client.get(f"/api/v1/loans/{loan['id']}/repayment-responsibilities")
    assert listed.status_code == 200
    assert {item["responsibility_percentage"] for item in listed.json()} == {
        "70.00",
        "30.00",
    }

    cashflow = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2020-02-01"},
    )
    body = cashflow.json()
    assert body["annual_loan_repayments"] == "36000.00"
    allocations = {item["display_name"]: item for item in body["loan_repayments"][0]["allocations"]}
    assert allocations["First payer"]["annual_amount"] == "25200.00"
    assert allocations["Second payer"]["annual_amount"] == "10800.00"
    changed = await client.post(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
        json={
            "person_id": second_person.json()["id"],
            "responsibility_percentage": 100,
            "effective_from": "2021-01-01",
        },
    )
    assert changed.status_code == 201
    changed_cashflow = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2021-02-01"},
    )
    changed_allocations = changed_cashflow.json()["loan_repayments"][0]["allocations"]
    assert len(changed_allocations) == 1
    assert changed_allocations[0]["display_name"] == "Second payer"
    assert changed_allocations[0]["annual_amount"] == "36000.00"
    other_household = await create_household(client, "Other household")
    outsider = await client.post(
        f"/api/v1/households/{other_household['id']}/people",
        json={"display_name": "Outside payer", "effective_from": "2020-01-01"},
    )
    rejected = await client.post(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
        json={
            "person_id": outsider.json()["id"],
            "responsibility_percentage": 100,
            "effective_from": "2020-01-01",
        },
    )
    assert rejected.status_code == 422


async def test_cashflow_preserves_inactive_repayment_responsibility(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    loan = await create_loan(client, loan_setup)
    inactive = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/people",
        json={
            "display_name": "Historical payer",
            "effective_from": "2019-01-01",
            "effective_to": "2019-12-31",
        },
    )
    active = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/people",
        json={"display_name": "Current payer", "effective_from": "2020-01-01"},
    )
    assert inactive.status_code == active.status_code == 201
    assigned = await client.post(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
        json={
            "person_id": inactive.json()["id"],
            "responsibility_percentage": 100,
            "effective_from": "2020-01-01",
        },
    )
    assert assigned.status_code == 201

    fully_inactive = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2020-02-01"},
    )
    projection = fully_inactive.json()["loan_repayments"][0]
    assert projection["allocations"][0]["display_name"] == "Historical payer"
    assert projection["allocations"][0]["responsibility_percentage"] == "100.00"
    assert "inactive people" in projection["warnings"][0]
    assert "Historical payer" in projection["warnings"][0]

    for person, percentage in ((inactive, 60), (active, 40)):
        response = await client.post(
            f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
            json={
                "person_id": person.json()["id"],
                "responsibility_percentage": percentage,
                "effective_from": "2021-01-01",
            },
        )
        assert response.status_code == 201
    partially_inactive = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2021-02-01"},
    )
    projection = partially_inactive.json()["loan_repayments"][0]
    allocations = {
        item["display_name"]: item["responsibility_percentage"]
        for item in projection["allocations"]
    }
    assert allocations == {"Historical payer": "60.00", "Current payer": "40.00"}
    assert any("Historical payer" in warning for warning in projection["warnings"])


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
    group = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Permission test", "property_id": loan_setup["property_id"]},
    )
    assert group.status_code == 201
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(loan_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()
    visible_groups = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups"
    )
    assert visible_groups.status_code == 200
    blocked_group = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/loan-groups",
        json={"display_name": "Viewer group", "property_id": loan_setup["property_id"]},
    )
    assert blocked_group.status_code == 403
    blocked_rename = await client.patch(
        f"/api/v1/loan-groups/{group.json()['id']}", json={"display_name": "Renamed"}
    )
    assert blocked_rename.status_code == 403
    blocked_removal = await client.delete(f"/api/v1/loan-groups/{group.json()['id']}")
    assert blocked_removal.status_code == 403
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
