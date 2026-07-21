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
    RetirementAccount,
)
from app.retirement_calculations import ContributionTerms, project_retirement
from tests.test_households import create_household


def test_retirement_projection_applies_contributions_tax_fees_and_adjustments() -> None:
    profile = ContributionTerms(
        effective_from=date(2025, 1, 1),
        effective_to=None,
        employer_rate=None,
        employer_amount=Decimal("12000"),
        voluntary_pre_tax_amount=Decimal("1200"),
        voluntary_post_tax_amount=Decimal("600"),
        contribution_tax_rate=Decimal("15"),
        annual_pre_tax_cap=Decimal("30000"),
    )
    entries, warnings = project_retirement(
        opening_balance=Decimal("100000"),
        opening_date=date(2025, 1, 1),
        projection_date=date(2026, 1, 1),
        annual_return_rate=Decimal("0"),
        annual_fees=Decimal("120"),
        annual_salary=Decimal("0"),
        profiles=[profile],
        adjustments=[(date(2025, 6, 15), Decimal("1000"))],
    )

    assert len(entries) == 12
    assert entries[-1].closing_balance == Decimal("112700.00")
    assert sum((entry.contribution_tax for entry in entries), Decimal("0")) == 1980
    assert warnings == []


def test_retirement_projection_warns_for_caps_and_rejects_invalid_range() -> None:
    profile = ContributionTerms(
        effective_from=date(2025, 1, 1),
        effective_to=None,
        employer_rate=Decimal("12"),
        employer_amount=None,
        voluntary_pre_tax_amount=Decimal("20000"),
        voluntary_post_tax_amount=Decimal("130000"),
        contribution_tax_rate=Decimal("15"),
        annual_pre_tax_cap=Decimal("30000"),
        annual_post_tax_cap=Decimal("120000"),
    )
    _, warnings = project_retirement(
        Decimal("0"),
        date(2025, 1, 1),
        date(2025, 2, 1),
        Decimal("0"),
        Decimal("0"),
        Decimal("100000"),
        [profile],
        [],
    )
    assert len(warnings) == 2
    with pytest.raises(ValueError, match="must not precede"):
        project_retirement(
            Decimal("0"),
            date(2025, 1, 1),
            date(2024, 1, 1),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            [],
            [],
        )


@pytest.fixture
async def retirement_types(session: AsyncSession) -> dict[str, LookupItem]:
    australian = LookupItem(
        category="retirement_account_type",
        code="AUSTRALIAN_SUP",
        display_name="Australian super",
        is_active=True,
    )
    generic = LookupItem(
        category="retirement_account_type",
        code="RETIREMENT_SAVINGS",
        display_name="Retirement savings",
        is_active=True,
    )
    session.add_all([australian, generic])
    await session.commit()
    return {"australian": australian, "generic": generic}


async def create_account(
    client: AsyncClient,
    household_id: str,
    account_type: LookupItem,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "display_name": "Future fund",
        "account_type_id": str(account_type.id),
        "opening_balance": 100000,
        "opening_balance_date": "2025-01-01",
        "expected_return_rate": 0,
        "annual_fees": 120,
    }
    payload.update(extra)
    response = await client.post(
        f"/api/v1/households/{household_id}/retirement-accounts", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_generic_retirement_account_contributions_events_and_projection(
    client: AsyncClient, retirement_types: dict[str, LookupItem]
) -> None:
    household = await create_household(client)
    account = await create_account(client, household["id"], retirement_types["generic"])
    assert account["currency"] == "AUD"
    contribution = await client.post(
        f"/api/v1/retirement-accounts/{account['id']}/contribution-profiles",
        json={
            "effective_from": "2025-01-01",
            "employer_amount": 12000,
            "voluntary_pre_tax_amount": 1200,
            "voluntary_post_tax_amount": 600,
            "contribution_tax_rate": 15,
        },
    )
    assert contribution.status_code == 201
    event = await client.post(
        f"/api/v1/retirement-accounts/{account['id']}/events",
        json={
            "effective_date": "2025-06-15",
            "amount": 1000,
            "idempotency_key": "opening-correction",
        },
    )
    assert event.status_code == 201
    projection = await client.get(
        f"/api/v1/retirement-accounts/{account['id']}/projection",
        params={"projection_date": "2026-01-01"},
    )
    assert projection.status_code == 200, projection.text
    body = projection.json()
    assert body["projected_balance"] == "112700.00"
    assert body["total_contributions"] == "13800.00"
    assert body["total_contribution_tax"] == "1980.00"
    assert len(body["entries"]) == 12
    listed = await client.get(f"/api/v1/households/{household['id']}/retirement-accounts")
    assert listed.json()[0]["id"] == account["id"]


async def test_australian_super_profile_rules_and_duplicate_inputs(
    client: AsyncClient, retirement_types: dict[str, LookupItem]
) -> None:
    household = await create_household(client)
    unsupported = await client.post(
        f"/api/v1/households/{household['id']}/retirement-accounts",
        json={
            "display_name": "Super",
            "account_type_id": str(retirement_types["australian"].id),
            "opening_balance": 0,
            "opening_balance_date": "2025-01-01",
            "expected_return_rate": 5,
            "provider_code": "MISSING_PROVIDER",
        },
    )
    assert unsupported.status_code == 422
    account = await create_account(
        client,
        household["id"],
        retirement_types["australian"],
        provider_code="au_super",
        provider_settings={"preservation_age": 60},
        retirement_age=67,
    )
    assert account["provider_code"] == "AU_SUPER"
    assert account["provider_settings"]["annual_pre_tax_cap"] == "30000"
    profile_url = f"/api/v1/retirement-accounts/{account['id']}/contribution-profiles"
    first = await client.post(profile_url, json={"effective_from": "2025-01-01"})
    assert first.status_code == 201
    overlap = await client.post(profile_url, json={"effective_from": "2025-06-01"})
    assert overlap.status_code == 409
    event_url = f"/api/v1/retirement-accounts/{account['id']}/events"
    event_payload = {
        "effective_date": "2025-03-01",
        "amount": -500,
        "idempotency_key": "correction",
    }
    assert (await client.post(event_url, json=event_payload)).status_code == 201
    assert (await client.post(event_url, json=event_payload)).status_code == 409


async def test_retirement_account_rejects_cross_household_person_and_hides_account(
    client: AsyncClient,
    session: AsyncSession,
    retirement_types: dict[str, LookupItem],
) -> None:
    household = await create_household(client)
    hidden_household = Household(display_name="Hidden", currency="NZD")
    session.add(hidden_household)
    await session.flush()
    hidden_person = Person(
        household_id=hidden_household.id,
        display_name="Hidden person",
        is_active=True,
        effective_from=date(2020, 1, 1),
    )
    session.add(hidden_person)
    await session.commit()
    invalid = await client.post(
        f"/api/v1/households/{household['id']}/retirement-accounts",
        json={
            "person_id": str(hidden_person.id),
            "display_name": "Invalid",
            "account_type_id": str(retirement_types["generic"].id),
            "opening_balance": 0,
            "opening_balance_date": "2025-01-01",
            "expected_return_rate": 5,
        },
    )
    assert invalid.status_code == 422
    hidden_account = RetirementAccount(
        household_id=hidden_household.id,
        display_name="Hidden account",
        account_type_id=retirement_types["generic"].id,
        currency="NZD",
        opening_balance=Decimal("100"),
        opening_balance_date=date(2025, 1, 1),
        expected_return_rate=Decimal("5"),
        annual_fees=Decimal("0"),
        is_active=True,
    )
    session.add(hidden_account)
    await session.commit()
    hidden = await client.get(
        f"/api/v1/retirement-accounts/{hidden_account.id}/projection",
        params={"projection_date": "2026-01-01"},
    )
    assert hidden.status_code == 404


async def test_retirement_writes_require_editor_role(
    client: AsyncClient,
    session: AsyncSession,
    retirement_types: dict[str, LookupItem],
) -> None:
    household = await create_household(client)
    account = await create_account(client, household["id"], retirement_types["generic"])
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(str(account["household_id"]))
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()

    update = await client.put(
        f"/api/v1/retirement-accounts/{account['id']}",
        json={
            "display_name": "Blocked",
            "expected_return_rate": 5,
            "annual_fees": 0,
            "is_active": True,
        },
    )
    contribution = await client.post(
        f"/api/v1/retirement-accounts/{account['id']}/contribution-profiles",
        json={"effective_from": "2025-01-01"},
    )
    event = await client.post(
        f"/api/v1/retirement-accounts/{account['id']}/events",
        json={"effective_date": "2025-01-01", "amount": 100},
    )

    assert update.status_code == 403
    assert contribution.status_code == 403
    assert event.status_code == 403
