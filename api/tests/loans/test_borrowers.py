"""Ordinary loan borrower and repayment-allocation tests."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HouseholdMembership, HouseholdRole
from tests.households.test_households import create_household
from tests.loans.test_loans import create_loan
from tests.loans.test_loans import loan_setup as loan_setup


async def create_person(
    client: AsyncClient,
    household_id: str,
    name: str,
    *,
    effective_to: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/households/{household_id}/people",
        json={
            "display_name": name,
            "effective_from": "2020-01-01",
            "effective_to": effective_to,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("borrower_count", "expected_percentages"),
    [
        (0, []),
        (1, ["100.00"]),
        (2, ["50.00", "50.00"]),
        (3, ["33.33", "33.33", "33.34"]),
    ],
)
async def test_borrowers_create_exact_default_cashflow_allocations(
    borrower_count: int,
    expected_percentages: list[str],
    client: AsyncClient,
    loan_setup: dict[str, str],
) -> None:
    people = [
        await create_person(client, loan_setup["household_id"], f"Borrower {index + 1}")
        for index in range(borrower_count)
    ]
    borrower_ids = [person["id"] for person in people]
    loan = await create_loan(client, loan_setup, borrower_person_ids=borrower_ids)

    assert loan["borrower_person_ids"] == borrower_ids
    listed = await client.get(f"/api/v1/loans/{loan['id']}")
    assert listed.status_code == 200
    assert listed.json()["borrower_person_ids"] == borrower_ids

    cashflow = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2020-02-01"},
    )
    assert cashflow.status_code == 200
    projection = cashflow.json()["loan_repayments"][0]
    percentages = sorted(item["responsibility_percentage"] for item in projection["allocations"])
    assert percentages == expected_percentages
    assert sum(
        (Decimal(item["responsibility_percentage"]) for item in projection["allocations"]),
        Decimal("0"),
    ) == (Decimal("100") if borrower_count else Decimal("0"))
    assert any("whole-household expense" in item for item in projection["warnings"]) is (
        borrower_count == 0
    )


async def test_advanced_override_precedes_borrowers_without_deleting_defaults(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    first = await create_person(client, loan_setup["household_id"], "Default first")
    second = await create_person(client, loan_setup["household_id"], "Default second")
    loan = await create_loan(
        client,
        loan_setup,
        borrower_person_ids=[first["id"], second["id"]],
    )
    override = await client.post(
        f"/api/v1/loans/{loan['id']}/repayment-responsibilities",
        json={
            "person_id": second["id"],
            "responsibility_percentage": 100,
            "effective_from": "2021-01-01",
            "effective_to": "2021-12-31",
        },
    )
    assert override.status_code == 201

    during = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2021-06-01"},
    )
    during_allocations = during.json()["loan_repayments"][0]["allocations"]
    assert [item["display_name"] for item in during_allocations] == ["Default second"]
    after = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2022-01-01"},
    )
    assert {
        item["display_name"]: item["responsibility_percentage"]
        for item in after.json()["loan_repayments"][0]["allocations"]
    } == {"Default first": "50.00", "Default second": "50.00"}


async def test_borrower_replacement_validates_access_and_audits(
    client: AsyncClient,
    session: AsyncSession,
    loan_setup: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = await create_person(client, loan_setup["household_id"], "First borrower")
    second = await create_person(client, loan_setup["household_id"], "Second borrower")
    loan = await create_loan(client, loan_setup, borrower_person_ids=[first["id"]])
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.loans.router.logger.info",
        lambda event, **values: events.append((event, values)),
    )

    replaced = await client.put(
        f"/api/v1/loans/{loan['id']}/borrowers",
        json={"borrower_person_ids": [second["id"]]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["borrower_person_ids"] == [second["id"]]
    assert events[-1][0] == "loan_borrowers_replaced"
    assert events[-1][1]["previous_borrower_person_ids"] == [first["id"]]
    assert events[-1][1]["resulting_borrower_person_ids"] == [second["id"]]

    other = await create_household(client, "Other borrower household")
    outsider = await create_person(client, other["id"], "Outside borrower")
    cross_household = await client.put(
        f"/api/v1/loans/{loan['id']}/borrowers",
        json={"borrower_person_ids": [outsider["id"]]},
    )
    assert cross_household.status_code == 422
    duplicate = await client.put(
        f"/api/v1/loans/{loan['id']}/borrowers",
        json={"borrower_person_ids": [second["id"], second["id"]]},
    )
    assert duplicate.status_code == 422

    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(loan_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()
    visible = await client.get(f"/api/v1/loans/{loan['id']}")
    assert visible.status_code == 200
    forbidden = await client.put(
        f"/api/v1/loans/{loan['id']}/borrowers",
        json={"borrower_person_ids": []},
    )
    assert forbidden.status_code == 403


async def test_inactive_borrower_keeps_allocation_provenance(
    client: AsyncClient, loan_setup: dict[str, str]
) -> None:
    inactive = await create_person(
        client,
        loan_setup["household_id"],
        "Historical borrower",
        effective_to="2020-01-15",
    )
    await create_loan(client, loan_setup, borrower_person_ids=[inactive["id"]])
    cashflow = await client.get(
        f"/api/v1/households/{loan_setup['household_id']}/cashflow",
        params={"as_of": "2020-02-01"},
    )
    projection = cashflow.json()["loan_repayments"][0]
    assert projection["allocations"][0]["display_name"] == "Historical borrower"
    assert any("Historical borrower" in warning for warning in projection["warnings"])
