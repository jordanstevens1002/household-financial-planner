import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Household, LookupItem, Person, Property
from tests.test_households import create_household


@pytest.fixture
async def property_lookups(session: AsyncSession) -> dict[str, str]:
    property_type = LookupItem(
        category="property_type", code="CUSTOM", display_name="Custom", is_active=True
    )
    status = LookupItem(
        category="property_status",
        code="OWNER_OCCUPIED",
        display_name="Owner occupied",
        is_active=True,
        is_occupied_by_household=True,
        is_active_asset=True,
    )
    session.add_all([property_type, status])
    await session.commit()
    return {"type": str(property_type.id), "status": str(status.id)}


def property_payload(lookups: dict[str, str]) -> dict[str, object]:
    return {
        "display_name": "Flexible property",
        "property_type_id": lookups["type"],
        "current_status_id": lookups["status"],
        "default_currency": "AUD",
    }


async def test_historical_purchase_wizard_creates_purchase_valuation(
    client: AsyncClient, property_lookups: dict[str, str]
) -> None:
    household = await create_household(client)
    payload = property_payload(property_lookups) | {
        "purchase_date": "2018-04-20",
        "purchase_price": "640000.00",
    }
    response = await client.post(
        f"/api/v1/households/{household['id']}/properties/wizard",
        json={
            "mode": "HISTORICAL_PURCHASE",
            "property": payload,
            "ownership": [
                {
                    "owner_type": "HOUSEHOLD",
                    "ownership_percentage": "100.00",
                    "effective_from": "2018-04-20",
                }
            ],
        },
    )
    assert response.status_code == 201
    assert response.json()["valuation"]["valuation_type"] == "PURCHASE_PRICE"
    assert response.json()["warnings"] == []
    assert response.json()["property"]["address_line_1"] is None


async def test_current_snapshot_wizard_accepts_no_loan_and_warns_on_incomplete_ownership(
    client: AsyncClient, property_lookups: dict[str, str]
) -> None:
    household = await create_household(client)
    response = await client.post(
        f"/api/v1/households/{household['id']}/properties/wizard",
        json={
            "mode": "CURRENT_SNAPSHOT",
            "property": property_payload(property_lookups),
            "baseline": {
                "baseline_date": "2026-07-16",
                "property_value": "900000.00",
                "loan_balance_total": "0.00",
                "status_id": property_lookups["status"],
            },
            "ownership": [
                {
                    "owner_type": "EXTERNAL_PARTY",
                    "external_owner_name": "Unrecorded co-owner",
                    "ownership_percentage": "40.00",
                    "effective_from": "2026-07-16",
                }
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["baseline"]["loan_balance_total"] == "0.00"
    assert "40.00% rather than 100.00%" in body["warnings"][0]


async def test_add_dated_ownership_reports_running_total(
    client: AsyncClient, property_lookups: dict[str, str]
) -> None:
    household = await create_household(client)
    created = await client.post(
        f"/api/v1/households/{household['id']}/properties",
        json=property_payload(property_lookups),
    )
    property_id = created.json()["id"]
    first = await client.post(
        f"/api/v1/properties/{property_id}/ownership",
        json={
            "owner_type": "HOUSEHOLD",
            "ownership_percentage": 60,
            "effective_from": "2020-01-01",
        },
    )
    second = await client.post(
        f"/api/v1/properties/{property_id}/ownership",
        json={"owner_type": "TRUST", "ownership_percentage": 40, "effective_from": "2020-01-01"},
    )
    assert first.json()["warnings"]
    assert second.json()["total_percentage"] == "100.00"
    assert second.json()["warnings"] == []


async def test_property_from_another_household_is_hidden(
    client: AsyncClient, session: AsyncSession, property_lookups: dict[str, str]
) -> None:
    await client.get("/api/v1/me")
    other_household = Household(display_name="Other", currency="AUD")
    session.add(other_household)
    await session.flush()
    hidden = Property(
        id=uuid.uuid4(),
        household_id=other_household.id,
        display_name="Hidden property",
        property_type_id=uuid.UUID(property_lookups["type"]),
        current_status_id=uuid.UUID(property_lookups["status"]),
        default_currency="AUD",
    )
    session.add(hidden)
    await session.commit()
    response = await client.get(f"/api/v1/properties/{hidden.id}")
    assert response.status_code == 404


async def test_wizard_validates_mode_and_lookup_categories(
    client: AsyncClient, property_lookups: dict[str, str]
) -> None:
    household = await create_household(client)
    invalid_mode = await client.post(
        f"/api/v1/households/{household['id']}/properties/wizard",
        json={"mode": "CURRENT_SNAPSHOT", "property": property_payload(property_lookups)},
    )
    assert invalid_mode.status_code == 422
    payload = property_payload(property_lookups)
    payload["property_type_id"] = property_lookups["status"]
    invalid_lookup = await client.post(
        f"/api/v1/households/{household['id']}/properties", json=payload
    )
    assert invalid_lookup.status_code == 422


async def test_wizard_rejects_person_from_another_household(
    client: AsyncClient, session: AsyncSession, property_lookups: dict[str, str]
) -> None:
    household = await create_household(client)
    other_household = Household(display_name="Other", currency="AUD")
    session.add(other_household)
    await session.flush()
    outsider = Person(
        household_id=other_household.id,
        display_name="Outsider",
        effective_from=date(2020, 1, 1),
        is_active=True,
    )
    session.add(outsider)
    await session.commit()
    response = await client.post(
        f"/api/v1/households/{household['id']}/properties/wizard",
        json={
            "mode": "HISTORICAL_PURCHASE",
            "property": property_payload(property_lookups)
            | {"purchase_date": "2020-01-01", "purchase_price": 500000},
            "ownership": [
                {
                    "owner_type": "PERSON",
                    "person_id": str(outsider.id),
                    "ownership_percentage": 100,
                    "effective_from": "2020-01-01",
                }
            ],
        },
    )
    assert response.status_code == 422


async def test_every_initial_property_type_can_be_used(
    client: AsyncClient, session: AsyncSession, property_lookups: dict[str, str]
) -> None:
    household = await create_household(client)
    codes = [
        "APARTMENT",
        "UNIT",
        "TOWNHOUSE",
        "SEMI_DETACHED",
        "TERRACE",
        "FREESTANDING_HOUSE",
        "DUPLEX",
        "VILLA",
        "RURAL_RESIDENTIAL",
        "FARM",
        "VACANT_LAND",
        "COMMERCIAL",
        "INDUSTRIAL",
        "RETAIL",
        "MIXED_USE",
        "HOLIDAY_PROPERTY",
        "OTHER",
    ]
    lookups = [
        LookupItem(category="property_type", code=code, display_name=code, is_active=True)
        for code in codes
    ]
    session.add_all(lookups)
    await session.commit()
    for item in lookups:
        response = await client.post(
            f"/api/v1/households/{household['id']}/properties",
            json=property_payload(property_lookups)
            | {"display_name": item.code, "property_type_id": str(item.id)},
        )
        assert response.status_code == 201
