"""Rental and property-expense tests."""

import uuid
from datetime import UTC, date, datetime

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
    assert body["gross_rent"] == "19760.00"
    assert body["rental_days"] == 365
    assert body["market_rent_equivalent"] == "22360.00"


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


async def test_owner_occupied_and_vacant_statuses_suppress_rent(
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
    property_id = (await create_property(client, rental_lookups, "owner"))["id"]
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
