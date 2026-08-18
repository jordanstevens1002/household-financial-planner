"""Rental and property-expense tests."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApplicationUser,
    EventClassification,
    EventType,
    FinancialEvent,
    Household,
    LookupItem,
    Property,
    PropertyExpense,
)
from tests.households.test_households import create_household


@pytest.fixture
async def rental_lookups(session: AsyncSession) -> dict[str, LookupItem]:
    property_type = LookupItem(
        category="property_type", code="DUPLEX_TEST", display_name="Duplex", is_active=True
    )
    partial = LookupItem(
        category="property_status",
        code="PARTIAL_TEST",
        display_name="Partially rented",
        is_active=True,
        generates_rental_income=True,
        applies_vacancy=True,
        applies_management_fee=True,
        applies_rental_expenses=True,
        is_occupied_by_household=True,
        is_active_asset=True,
    )
    rented = LookupItem(
        category="property_status",
        code="RENTED_TEST",
        display_name="Rented",
        is_active=True,
        generates_rental_income=True,
        applies_vacancy=True,
        applies_management_fee=True,
        applies_rental_expenses=True,
        is_occupied_by_household=False,
        is_active_asset=True,
    )
    owner = LookupItem(
        category="property_status",
        code="OWNER_TEST",
        display_name="Owner occupied",
        is_active=True,
        generates_rental_income=False,
        applies_vacancy=False,
        applies_management_fee=False,
        applies_rental_expenses=False,
        is_occupied_by_household=True,
        is_active_asset=True,
    )
    family = LookupItem(
        category="property_status",
        code="FAMILY_RENT_TEST",
        display_name="Family occupied with rent",
        is_active=True,
        generates_rental_income=True,
        applies_vacancy=False,
        applies_management_fee=False,
        applies_rental_expenses=False,
        is_occupied_by_household=False,
        is_active_asset=True,
    )
    vacant = LookupItem(
        category="property_status",
        code="VACANT_TEST",
        display_name="Vacant",
        is_active=True,
        generates_rental_income=False,
        applies_vacancy=False,
        applies_management_fee=False,
        applies_rental_expenses=True,
        is_occupied_by_household=False,
        is_active_asset=True,
    )
    expense_type = LookupItem(
        category="property_expense_type",
        code="INSURANCE_TEST",
        display_name="Insurance",
        is_active=True,
    )
    session.add_all([property_type, partial, rented, owner, family, vacant, expense_type])
    await session.commit()
    return {
        "type": property_type,
        "partial": partial,
        "rented": rented,
        "owner": owner,
        "family": family,
        "vacant": vacant,
        "expense": expense_type,
    }


async def create_property(
    client: AsyncClient, lookups: dict[str, LookupItem], status_name: str = "partial"
) -> dict[str, object]:
    household = await create_household(client)
    response = await client.post(
        f"/api/v1/households/{household['id']}/properties",
        json={
            "display_name": "Mixed-use home",
            "property_type_id": str(lookups["type"].id),
            "current_status_id": str(lookups[status_name].id),
        },
    )
    assert response.status_code == 201
    return response.json()


def profile(
    name: str,
    amount: int,
    share: int,
    start: str = "2025-01-01",
    end: str | None = "2025-12-31",
) -> dict[str, object]:
    return {
        "display_name": name,
        "effective_from": start,
        "effective_to": end,
        "market_rent_amount": amount + 50,
        "charged_rent_amount": amount,
        "frequency": "WEEKLY",
        "vacancy_rate": 5,
        "management_fee_rate": 8,
        "rental_share_percentage": share,
    }


async def test_partial_rental_supports_concurrent_duplex_granny_flat_and_roommate_streams(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_record = await create_property(client, rental_lookups)
    property_id = property_record["id"]
    for payload in (
        profile("Duplex unit B", 500, 50),
        profile("Granny flat", 300, 30),
        profile("Roommate room", 200, 20),
    ):
        response = await client.post(
            f"/api/v1/properties/{property_id}/rental-profiles", json=payload
        )
        assert response.status_code == 201
    result = await client.get(
        f"/api/v1/properties/{property_id}/cashflow",
        params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["gross_rent"] == "52000.00"
    assert body["rental_days"] == 365
    assert body["market_rent_equivalent"] == "59800.00"


async def test_standard_whole_property_rental_applies_vacancy_and_management_fees(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_id = (await create_property(client, rental_lookups, "rented"))["id"]
    created = await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Whole home", 500, 100),
    )
    assert created.status_code == 201

    result = await client.get(
        f"/api/v1/properties/{property_id}/cashflow",
        params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["gross_rent"] == "26000.00"
    assert body["vacancy_cost"] == "1300.00"
    assert body["management_fee"] == "1976.00"
    assert body["net_cashflow"] == "22724.00"
    assert body["market_rent_equivalent"] == "28600.00"
    assert body["charged_rent_equivalent"] == "26000.00"
    assert body["rent_difference"] == "-2600.00"
    assert body["rental_days"] == 365
    assert "Recurring amounts use a 365-day planning year for daily allocation" in body["warnings"]


async def test_concurrent_rental_shares_cannot_exceed_whole_property(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_id = (await create_property(client, rental_lookups))["id"]
    first = await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Main tenancy", 500, 80),
    )
    excessive = await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Granny flat", 250, 30),
    )
    assert first.status_code == 201
    assert excessive.status_code == 422


async def test_owner_occupied_partial_rental_uses_the_portion_rent_without_apportioning_twice(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_id = (await create_property(client, rental_lookups, "owner"))["id"]
    payload = profile("Granny flat", 350, 30)
    payload.update(
        market_rent_amount=400,
        vacancy_rate=3,
        management_fee_rate=7.5,
        effective_from="2025-01-01",
        effective_to="2025-12-31",
    )
    assert (
        await client.post(f"/api/v1/properties/{property_id}/rental-profiles", json=payload)
    ).status_code == 201
    body = (
        await client.get(
            f"/api/v1/properties/{property_id}/cashflow",
            params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
        )
    ).json()
    assert body["gross_rent"] == "18200.00"
    assert body["market_rent_equivalent"] == "20800.00"
    assert body["vacancy_cost"] == "546.00"
    assert body["management_fee"] == "1324.05"
    assert body["net_cashflow"] == "16329.95"


async def test_vacant_and_whole_owner_occupied_profiles_suppress_rent(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    for status_name in ("owner", "vacant"):
        property_id = (await create_property(client, rental_lookups, status_name))["id"]
        await client.post(
            f"/api/v1/properties/{property_id}/rental-profiles",
            json=profile("Inactive tenancy", 500, 100),
        )
        result = await client.get(
            f"/api/v1/properties/{property_id}/cashflow",
            params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
        )
        assert result.json()["gross_rent"] == "0.00"


async def test_ongoing_rental_can_be_corrected_closed_and_replaced(
    client: AsyncClient,
    rental_lookups: dict[str, LookupItem],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.rental.router.logger.info",
        lambda event, **values: audit_events.append((event, values)),
    )
    property_id = (await create_property(client, rental_lookups, "rented"))["id"]
    original = profile("Whole home", 500, 100, end=None)
    created = await client.post(f"/api/v1/properties/{property_id}/rental-profiles", json=original)
    assert created.status_code == 201

    corrected = await client.patch(
        f"/api/v1/properties/{property_id}/rental-profiles/{created.json()['id']}",
        json={"charged_rent_amount": 525, "effective_to": "2025-06-30"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["charged_rent_amount"] == "525.00"
    assert corrected.json()["effective_to"] == "2025-06-30"
    event, values = audit_events[-1]
    assert event == "rental_profile_corrected"
    assert values["actor_user_id"]
    assert values["property_id"] == property_id
    assert values["changed_fields"] == ["charged_rent_amount", "effective_to"]

    replacement = await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Whole home", 550, 100, "2025-07-01", None),
    )
    assert replacement.status_code == 201
    records = (await client.get(f"/api/v1/properties/{property_id}/rental-profiles")).json()
    assert [(item["charged_rent_amount"], item["effective_to"]) for item in records] == [
        ("525.00", "2025-06-30"),
        ("550.00", None),
    ]


async def test_family_occupancy_can_charge_rent_without_vacancy_or_management(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_id = (await create_property(client, rental_lookups, "family"))["id"]
    await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Family arrangement", 400, 100),
    )
    body = (
        await client.get(
            f"/api/v1/properties/{property_id}/cashflow",
            params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
        )
    ).json()
    assert body["gross_rent"] == "20800.00"
    assert body["vacancy_cost"] == "0.00"
    assert body["management_fee"] == "0.00"


async def test_profiles_are_dated_and_future_rent_does_not_leak_into_history(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_id = (await create_property(client, rental_lookups))["id"]
    await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Room", 350, 50, "2025-07-01", "2025-12-31"),
    )
    before = await client.get(
        f"/api/v1/properties/{property_id}/cashflow",
        params={"from_date": "2025-01-01", "to_date": "2025-06-30"},
    )
    after = await client.get(
        f"/api/v1/properties/{property_id}/cashflow",
        params={"from_date": "2025-07-01", "to_date": "2025-12-31"},
    )
    assert before.json()["gross_rent"] == "0.00"
    assert before.json()["warnings"]
    assert after.json()["rental_days"] == 184
    assert after.json()["gross_rent"] != "0.00"


async def test_dated_status_change_activates_partial_rent_without_rewriting_history(
    client: AsyncClient,
    session: AsyncSession,
    rental_lookups: dict[str, LookupItem],
) -> None:
    property_id = (await create_property(client, rental_lookups, "vacant"))["id"]
    await client.post(
        f"/api/v1/properties/{property_id}/rental-profiles",
        json=profile("Roommate room", 300, 25),
    )
    await client.get("/api/v1/me")
    user = await session.scalar(
        select(ApplicationUser).where(ApplicationUser.oidc_subject == "test-user")
    )
    event_type = EventType(
        code="PROPERTY_STATUS_CHANGED",
        display_name="Property status changed",
        priority=10,
        is_active=True,
    )
    session.add(event_type)
    await session.flush()
    assert user is not None
    property_record = await session.get(Property, uuid.UUID(str(property_id)))
    assert property_record is not None
    session.add(
        FinancialEvent(
            household_id=property_record.household_id,
            event_type_id=event_type.id,
            effective_at=datetime(2025, 7, 1, tzinfo=UTC),
            property_id=uuid.UUID(str(property_id)),
            payload={"status_id": str(rental_lookups["partial"].id)},
            classification=EventClassification.OBSERVED,
            is_enabled=True,
            data_quality_flags=[],
            created_by_user_id=user.id,
        )
    )
    await session.commit()
    body = (
        await client.get(
            f"/api/v1/properties/{property_id}/cashflow",
            params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
        )
    ).json()
    assert body["rental_days"] == 184
    assert body["gross_rent"] != "0.00"


async def test_rental_and_whole_property_expenses_follow_status_flags(
    client: AsyncClient, rental_lookups: dict[str, LookupItem]
) -> None:
    property_id = (await create_property(client, rental_lookups, "owner"))["id"]
    base = {
        "expense_type_id": str(rental_lookups["expense"].id),
        "amount": 1200,
        "frequency": "ANNUAL",
        "effective_from": "2025-01-01",
        "effective_to": "2025-12-31",
    }
    for name, rental_only in (("Insurance", False), ("Renter-related cost", True)):
        response = await client.post(
            f"/api/v1/properties/{property_id}/expenses",
            json=base | {"display_name": name, "is_rental_expense": rental_only},
        )
        assert response.status_code == 201
    body = (
        await client.get(
            f"/api/v1/properties/{property_id}/cashflow",
            params={"from_date": "2025-01-01", "to_date": "2025-12-31"},
        )
    ).json()
    assert body["property_expenses"] == "1200.00"
    assert body["net_cashflow"] == "-1200.00"


async def test_property_expense_can_be_corrected_removed_and_is_audited(
    client: AsyncClient,
    session: AsyncSession,
    rental_lookups: dict[str, LookupItem],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.rental.router.logger.info",
        lambda event, **values: audit_events.append((event, values)),
    )
    property_id = (await create_property(client, rental_lookups, "rented"))["id"]
    payload = {
        "expense_type_id": str(rental_lookups["expense"].id),
        "display_name": "Insurance",
        "amount": 1200,
        "frequency": "ANNUAL",
        "effective_from": "2025-01-01",
        "effective_to": None,
        "is_rental_expense": False,
    }
    created = await client.post(f"/api/v1/properties/{property_id}/expenses", json=payload)
    assert created.status_code == 201
    expense_id = created.json()["id"]

    corrected = await client.patch(
        f"/api/v1/properties/{property_id}/expenses/{expense_id}",
        json={"amount": 1300, "effective_to": "2025-12-31"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["amount"] == "1300.00"
    assert corrected.json()["effective_to"] == "2025-12-31"
    assert audit_events[-1][0] == "property_expense_updated"
    assert audit_events[-1][1]["actor_user_id"]
    assert audit_events[-1][1]["property_id"] == property_id
    assert audit_events[-1][1]["before"]["amount"] == "1200.00"
    assert audit_events[-1][1]["after"]["amount"] == "1300.00"

    revisions = list(
        await session.scalars(
            select(PropertyExpense)
            .where(PropertyExpense.property_id == uuid.UUID(property_id))
            .order_by(PropertyExpense.effective_from, PropertyExpense.id)
        )
    )
    assert len(revisions) == 2
    original = next(item for item in revisions if str(item.id) == expense_id)
    replacement = next(item for item in revisions if str(item.id) != expense_id)
    assert original.amount == Decimal("1200.00")
    assert original.superseded_at is not None
    assert replacement.replaces_id == original.id
    assert replacement.amount == Decimal("1300.00")

    removed = await client.delete(
        f"/api/v1/properties/{property_id}/expenses/{corrected.json()['id']}"
    )
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/properties/{property_id}/expenses")).json() == []
    assert audit_events[-1][0] == "property_expense_deleted"
    assert audit_events[-1][1]["before"]["display_name"] == "Insurance"
    await session.refresh(replacement)
    assert replacement.deleted_at is not None


async def test_inactive_expense_type_can_be_closed_but_not_newly_selected(
    client: AsyncClient,
    session: AsyncSession,
    rental_lookups: dict[str, LookupItem],
) -> None:
    property_id = (await create_property(client, rental_lookups, "rented"))["id"]
    payload = {
        "expense_type_id": str(rental_lookups["expense"].id),
        "display_name": "Retired fee",
        "amount": 100,
        "frequency": "ANNUAL",
        "effective_from": "2025-01-01",
        "is_rental_expense": True,
    }
    created = await client.post(f"/api/v1/properties/{property_id}/expenses", json=payload)
    assert created.status_code == 201
    rental_lookups["expense"].is_active = False
    await session.commit()

    closed = await client.patch(
        f"/api/v1/properties/{property_id}/expenses/{created.json()['id']}",
        json={"effective_to": "2025-12-31"},
    )
    assert closed.status_code == 200
    assert closed.json()["effective_to"] == "2025-12-31"

    rejected = await client.post(f"/api/v1/properties/{property_id}/expenses", json=payload)
    assert rejected.status_code == 422


async def test_other_household_cannot_access_rental_records(
    client: AsyncClient, session: AsyncSession, rental_lookups: dict[str, LookupItem]
) -> None:
    await client.get("/api/v1/me")
    other = Household(display_name="Other", currency="NZD")
    session.add(other)
    await session.flush()
    hidden = Property(
        household_id=other.id,
        display_name="Hidden property",
        property_type_id=rental_lookups["type"].id,
        current_status_id=rental_lookups["partial"].id,
        default_currency="NZD",
    )
    session.add(hidden)
    await session.commit()
    assert (await client.get(f"/api/v1/properties/{hidden.id}/rental-profiles")).status_code == 404
    assert (
        await client.post(
            f"/api/v1/properties/{hidden.id}/expenses",
            json={
                "expense_type_id": str(rental_lookups["expense"].id),
                "display_name": "Hidden",
                "amount": 1,
                "frequency": "ONCE",
                "effective_from": date.today().isoformat(),
                "is_rental_expense": False,
            },
        )
    ).status_code == 404
