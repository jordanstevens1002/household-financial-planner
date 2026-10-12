"""Retirement projection tests."""

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
    RetirementAccountRevision,
)
from app.retirement.calculations import ContributionTerms, project_retirement
from tests.households.test_households import create_household


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
        code="AUSTRALIAN_SUPER",
        display_name="Australian superannuation",
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


async def test_retirement_provider_catalogue_is_discoverable(client: AsyncClient) -> None:
    response = await client.get("/api/v1/retirement-providers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "code": "AU_SUPER",
            "display_name": "Australian superannuation",
            "supported_account_type_codes": ["AUSTRALIAN_SUPER", "SELF_MANAGED_SUPER_FUND"],
        }
    ]


async def test_retirement_account_correction_preserves_audit_history_and_rejects_stale_write(
    client: AsyncClient,
    session: AsyncSession,
    retirement_types: dict[str, LookupItem],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    household = await create_household(client)
    audit_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.retirement.router.logger.info",
        lambda event, **values: audit_events.append((event, values)),
    )
    account = await create_account(client, household["id"], retirement_types["generic"])
    created_event, created_values = audit_events[-1]
    assert created_event == "retirement_account_created"
    assert created_values["actor_user_id"]
    assert created_values["household_id"] == household["id"]
    assert created_values["account_type_id"] == str(retirement_types["generic"].id)
    payload = {
        "expected_revision": 1,
        "person_id": None,
        "display_name": "Corrected fund",
        "account_type_id": str(retirement_types["australian"].id),
        "currency": "NZD",
        "opening_balance": "125000.00",
        "opening_balance_date": "2025-02-01",
        "expected_return_rate": "5.5000",
        "annual_fees": "200.00",
        "retirement_age": 65,
        "provider_code": "AU_SUPER",
        "provider_settings": {},
        "is_active": True,
        "notes": "corrected",
    }
    corrected = await client.put(f"/api/v1/retirement-accounts/{account['id']}", json=payload)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["revision"] == 2
    assert corrected.json()["currency"] == "NZD"
    assert corrected.json()["opening_balance"] == "125000.00"
    stale = await client.put(f"/api/v1/retirement-accounts/{account['id']}", json=payload)
    assert stale.status_code == 409
    revisions = list(
        await session.scalars(
            select(RetirementAccountRevision)
            .where(RetirementAccountRevision.retirement_account_id == uuid.UUID(account["id"]))
            .order_by(RetirementAccountRevision.created_at)
        )
    )
    assert [item.action for item in revisions] == ["CREATED", "CORRECTED"]
    assert revisions[1].previous_state["currency"] == "AUD"
    assert revisions[1].resulting_state["currency"] == "NZD"
    assert audit_events[-1][0] == "retirement_account_corrected"
    assert audit_events[-1][1]["household_id"] == household["id"]


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
    incompatible = await client.post(
        f"/api/v1/households/{household['id']}/retirement-accounts",
        json={
            "display_name": "Generic savings",
            "account_type_id": str(retirement_types["generic"].id),
            "opening_balance": 0,
            "opening_balance_date": "2025-01-01",
            "expected_return_rate": 5,
            "provider_code": "AU_SUPER",
        },
    )
    assert incompatible.status_code == 422
    assert "supports AUSTRALIAN_SUPER" in incompatible.json()["detail"]
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
            "expected_revision": 1,
            "person_id": None,
            "display_name": "Blocked",
            "account_type_id": str(retirement_types["generic"].id),
            "currency": "AUD",
            "opening_balance": 100000,
            "opening_balance_date": "2025-01-01",
            "expected_return_rate": 5,
            "annual_fees": 0,
            "retirement_age": None,
            "provider_code": None,
            "provider_settings": {},
            "is_active": True,
            "notes": None,
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
