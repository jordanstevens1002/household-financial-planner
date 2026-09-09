"""Durable correction and closure tests for repayment allocation sets."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    HouseholdMembership,
    HouseholdRole,
    LoanRepaymentResponsibilityRevision,
)
from tests.loans.test_borrowers import create_person
from tests.loans.test_loans import create_loan, replace_repayment_responsibilities
from tests.loans.test_loans import loan_setup as loan_setup


async def test_replacement_history_preserves_complete_allocation_snapshots(
    client: AsyncClient,
    session: AsyncSession,
    loan_setup: dict[str, str],
) -> None:
    first = await create_person(client, loan_setup["household_id"], "First payer")
    second = await create_person(client, loan_setup["household_id"], "Second payer")
    loan = await create_loan(client, loan_setup)
    initial = await replace_repayment_responsibilities(
        client,
        str(loan["id"]),
        "2021-01-01",
        [(str(first["id"]), 60), (str(second["id"]), 40)],
        effective_to="2021-12-31",
    )
    assert initial.status_code == 200
    replacement = await replace_repayment_responsibilities(
        client,
        str(loan["id"]),
        "2021-01-01",
        [(str(second["id"]), 100)],
        effective_to="2021-09-30",
    )
    assert replacement.status_code == 200

    response = await client.get(f"/api/v1/loans/{loan['id']}/repayment-responsibility-revisions")
    assert response.status_code == 200
    assert response.json()["next_cursor"] is None
    revisions = response.json()["items"]
    assert [item["action"] for item in revisions] == ["CREATED", "REPLACED"]
    assert len({item["actor_user_id"] for item in revisions}) == 1
    assert all(item["created_at"] for item in revisions)
    assert revisions[0]["previous_allocations"] == []
    assert revisions[0]["resulting_allocations"][0]["effective_to"] == "2021-12-31"
    previous = {item["person_id"]: item for item in revisions[1]["previous_allocations"]}
    assert previous[first["id"]]["responsibility_percentage"] == "60.00"
    assert previous[second["id"]]["responsibility_percentage"] == "40.00"
    assert {item["effective_to"] for item in previous.values()} == {"2021-12-31"}

    stored = list(
        await session.scalars(
            select(LoanRepaymentResponsibilityRevision).where(
                LoanRepaymentResponsibilityRevision.loan_id == uuid.UUID(str(loan["id"]))
            )
        )
    )
    assert len(stored) == 2


async def test_closure_restores_borrower_defaults_without_changing_past_results(
    client: AsyncClient,
    loan_setup: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = await create_person(client, loan_setup["household_id"], "Default first")
    second = await create_person(client, loan_setup["household_id"], "Default second")
    loan = await create_loan(
        client,
        loan_setup,
        borrower_person_ids=[first["id"], second["id"]],
    )
    sensitive_note = "Private closure arrangement"
    override = await client.put(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2021-01-01",
        json={
            "allocations": [
                {
                    "person_id": second["id"],
                    "responsibility_percentage": 100,
                    "notes": sensitive_note,
                }
            ]
        },
    )
    assert override.status_code == 200
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.loans.router.logger.info",
        lambda event, **values: events.append((event, values)),
    )

    closure = await client.patch(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2021-01-01/closure",
        json={"effective_to": "2021-06-30"},
    )
    assert closure.status_code == 200, closure.text
    assert closure.json()["effective_to"] == "2021-06-30"
    assert events[-1][0] == "loan_repayment_responsibility_set_closed"
    assert sensitive_note not in repr(events[-1])

    during = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2021-06-01"},
    )
    assert [
        item["display_name"] for item in during.json()["loan_repayments"][0]["allocations"]
    ] == ["Default second"]
    after = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2021-07-01"},
    )
    assert {
        item["display_name"]: item["responsibility_percentage"]
        for item in after.json()["loan_repayments"][0]["allocations"]
    } == {"Default first": "50.00", "Default second": "50.00"}

    future = await replace_repayment_responsibilities(
        client,
        str(loan["id"]),
        "2022-01-01",
        [(str(first["id"]), 100)],
    )
    assert future.status_code == 200
    unchanged_past = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2021-06-01"},
    )
    assert [
        item["display_name"] for item in unchanged_past.json()["loan_repayments"][0]["allocations"]
    ] == ["Default second"]

    revisions = await client.get(f"/api/v1/loans/{loan['id']}/repayment-responsibility-revisions")
    assert [item["action"] for item in revisions.json()["items"]] == [
        "CREATED",
        "CLOSED",
        "CREATED",
    ]
    closed = revisions.json()["items"][1]
    assert closed["previous_allocations"][0]["effective_to"] is None
    assert closed["previous_allocations"][0]["notes"] == sensitive_note
    assert closed["resulting_allocations"][0]["effective_to"] == "2021-06-30"

    actions: list[str] = []
    cursor = None
    while True:
        page = await client.get(
            f"/api/v1/loans/{loan['id']}/repayment-responsibility-revisions",
            params={"limit": 1, **({"cursor": cursor} if cursor else {})},
        )
        assert page.status_code == 200
        payload = page.json()
        assert len(payload["items"]) == 1
        actions.append(payload["items"][0]["action"])
        cursor = payload["next_cursor"]
        if cursor is None:
            break
    assert actions == ["CREATED", "CLOSED", "CREATED"]

    invalid_cursor = await client.get(
        f"/api/v1/loans/{loan['id']}/repayment-responsibility-revisions",
        params={"cursor": "not-a-cursor"},
    )
    assert invalid_cursor.status_code == 422
    excessive_limit = await client.get(
        f"/api/v1/loans/{loan['id']}/repayment-responsibility-revisions",
        params={"limit": 101},
    )
    assert excessive_limit.status_code == 422


async def test_closure_validates_interval_existence_and_editor_access(
    client: AsyncClient,
    session: AsyncSession,
    loan_setup: dict[str, str],
) -> None:
    person = await create_person(client, loan_setup["household_id"], "Payer")
    loan = await create_loan(client, loan_setup)
    missing = await client.patch(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2021-01-01/closure",
        json={"effective_to": "2021-06-30"},
    )
    assert missing.status_code == 404
    created = await replace_repayment_responsibilities(
        client,
        str(loan["id"]),
        "2021-01-01",
        [(str(person["id"]), 100)],
        effective_to="2021-12-31",
    )
    assert created.status_code == 200
    reversed_interval = await client.patch(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2021-01-01/closure",
        json={"effective_to": "2020-12-31"},
    )
    assert reversed_interval.status_code == 422
    extension = await client.patch(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2021-01-01/closure",
        json={"effective_to": "2022-01-01"},
    )
    assert extension.status_code == 409

    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(loan_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()
    forbidden = await client.patch(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities/2021-01-01/closure",
        json={"effective_to": "2021-06-30"},
    )
    assert forbidden.status_code == 403
