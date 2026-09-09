"""Atomic dated loan repayment-allocation set tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HouseholdMembership, HouseholdRole
from tests.loans.test_borrowers import create_person
from tests.loans.test_loans import create_loan, replace_repayment_responsibilities
from tests.loans.test_loans import loan_setup as loan_setup


async def test_same_date_set_is_replaced_atomically_and_audited(
    client: AsyncClient,
    loan_setup: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = await create_person(client, loan_setup["household_id"], "First payer")
    second = await create_person(client, loan_setup["household_id"], "Second payer")
    loan = await create_loan(client, loan_setup)
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.loans.router.logger.info",
        lambda event, **values: events.append((event, values)),
    )

    sensitive_note = "Private repayment arrangement"
    initial = await client.put(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2026-01-01",
        json={
            "allocations": [
                {
                    "person_id": first["id"],
                    "responsibility_percentage": 60,
                    "notes": sensitive_note,
                },
                {"person_id": second["id"], "responsibility_percentage": 40},
            ]
        },
    )
    assert initial.status_code == 200, initial.text
    initial_ids = {responsibility["id"] for responsibility in initial.json()["responsibilities"]}
    assert initial.json()["total_percentage"] == "100"
    assert initial.json()["warnings"] == []

    replacement = await replace_repayment_responsibilities(
        client,
        str(loan["id"]),
        "2026-01-01",
        [(str(second["id"]), 100)],
    )
    assert replacement.status_code == 200, replacement.text
    listed = await client.get(f"/api/v1/loans/{loan['id']}/repayment-responsibilities")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["person_id"] == second["id"]
    assert listed.json()[0]["id"] not in initial_ids

    event, values = events[-1]
    assert event == "loan_repayment_responsibility_set_replaced"
    assert values["actor_user_id"]
    assert values["household_id"] == loan_setup["household_id"]
    assert values["loan_id"] == loan["id"]
    assert set(values["previous_responsibility_ids"]) == initial_ids
    previous_by_person = {
        allocation["person_id"]: allocation for allocation in values["previous_allocations"]
    }
    assert previous_by_person == {
        first["id"]: {
            "person_id": first["id"],
            "responsibility_percentage": "60.00",
            "effective_to": None,
        },
        second["id"]: {
            "person_id": second["id"],
            "responsibility_percentage": "40.00",
            "effective_to": None,
        },
    }
    assert values["allocations"] == [
        {
            "person_id": second["id"],
            "responsibility_percentage": "100.00",
            "effective_to": None,
        }
    ]
    assert sensitive_note not in repr(events)
    revisions = await client.get(f"/api/v1/loans/{loan['id']}/repayment-responsibility-revisions")
    assert revisions.json()["items"][0]["resulting_allocations"][0]["notes"] == sensitive_note


async def test_set_validation_rejects_partial_duplicate_and_invalid_intervals(
    client: AsyncClient,
    loan_setup: dict[str, str],
) -> None:
    person = await create_person(client, loan_setup["household_id"], "Payer")
    loan = await create_loan(client, loan_setup)
    url = f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2026-01-01"

    partial = await client.put(
        url,
        json={"allocations": [{"person_id": person["id"], "responsibility_percentage": 99.99}]},
    )
    assert partial.status_code == 422
    assert "total exactly 100 percent" in partial.text

    duplicate = await client.put(
        url,
        json={
            "allocations": [
                {"person_id": person["id"], "responsibility_percentage": 50},
                {"person_id": person["id"], "responsibility_percentage": 50},
            ]
        },
    )
    assert duplicate.status_code == 422
    assert "person IDs must be unique" in duplicate.text

    reversed_dates = await client.put(
        url,
        json={
            "effective_to": "2025-12-31",
            "allocations": [{"person_id": person["id"], "responsibility_percentage": 100}],
        },
    )
    assert reversed_dates.status_code == 422
    assert "effective_to must not precede" in reversed_dates.text


@pytest.mark.parametrize(
    "person_payload",
    [
        {"display_name": "Future", "effective_from": "2026-02-01"},
        {
            "display_name": "Expired",
            "effective_from": "2025-01-01",
            "effective_to": "2026-01-15",
        },
        {
            "display_name": "Disabled",
            "effective_from": "2025-01-01",
            "is_active": False,
        },
    ],
)
async def test_set_requires_people_active_for_the_complete_interval(
    person_payload: dict[str, object],
    client: AsyncClient,
    loan_setup: dict[str, str],
) -> None:
    person = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/people",
        json=person_payload,
    )
    assert person.status_code == 201
    loan = await create_loan(client, loan_setup)
    response = await client.put(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2026-01-01",
        json={
            "effective_to": "2026-01-31",
            "allocations": [
                {
                    "person_id": person.json()["id"],
                    "responsibility_percentage": 100,
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "active for the complete allocation interval" in response.text


async def test_disabled_person_can_be_used_for_their_finite_historical_interval(
    client: AsyncClient,
    loan_setup: dict[str, str],
) -> None:
    person = await client.post(
        f"/api/v1/households/{loan_setup['household_id']}/people",
        json={
            "display_name": "Former payer",
            "effective_from": "2020-01-01",
            "effective_to": "2021-12-31",
            "is_active": False,
        },
    )
    assert person.status_code == 201
    loan = await create_loan(client, loan_setup)

    historical = await client.put(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2020-01-01",
        json={
            "effective_to": "2021-12-31",
            "allocations": [
                {
                    "person_id": person.json()["id"],
                    "responsibility_percentage": 100,
                }
            ],
        },
    )
    assert historical.status_code == 200, historical.text

    open_ended = await client.put(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2020-01-01",
        json={
            "allocations": [
                {
                    "person_id": person.json()["id"],
                    "responsibility_percentage": 100,
                }
            ],
        },
    )
    assert open_ended.status_code == 422


async def test_viewer_cannot_replace_repayment_set(
    client: AsyncClient,
    session: AsyncSession,
    loan_setup: dict[str, str],
) -> None:
    person = await create_person(client, loan_setup["household_id"], "Payer")
    loan = await create_loan(client, loan_setup)
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(loan_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()

    response = await replace_repayment_responsibilities(
        client,
        str(loan["id"]),
        "2026-01-01",
        [(str(person["id"]), 100)],
    )
    assert response.status_code == 403
