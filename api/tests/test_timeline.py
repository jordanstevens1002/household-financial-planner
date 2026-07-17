import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EventClassification,
    EventType,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    Property,
    PropertyBaseline,
)
from app.timeline import event_quality_flags, temporal_position
from tests.test_households import create_household


@pytest.fixture
async def timeline_setup(client: AsyncClient, session: AsyncSession) -> dict[str, str]:
    household = await create_household(client)
    property_type = LookupItem(
        category="property_type", code="TIMELINE_TYPE", display_name="Timeline", is_active=True
    )
    active = LookupItem(
        category="property_status",
        code="TIMELINE_ACTIVE",
        display_name="Active",
        is_active=True,
        is_active_asset=True,
    )
    sold = LookupItem(
        category="property_status",
        code="TIMELINE_SOLD",
        display_name="Sold",
        is_active=True,
        is_active_asset=False,
    )
    event_types = [
        EventType(code="PROPERTY_STATUS_CHANGED", display_name="Status", priority=10),
        EventType(code="PROPERTY_VALUED", display_name="Valued", priority=20),
        EventType(code="PROPERTY_SOLD", display_name="Sold", priority=30),
        EventType(code="CUSTOM_EVENT", display_name="Custom", priority=100),
    ]
    session.add_all([property_type, active, sold, *event_types])
    await session.flush()
    property_record = Property(
        household_id=uuid.UUID(household["id"]),
        display_name="Timeline property",
        property_type_id=property_type.id,
        current_status_id=active.id,
        default_currency="AUD",
    )
    session.add(property_record)
    await session.flush()
    baseline = PropertyBaseline(
        property_id=property_record.id,
        baseline_date=date(2020, 1, 1),
        property_value=400000,
        loan_balance_total=200000,
        status_id=active.id,
    )
    session.add(baseline)
    await session.commit()
    return {
        "household_id": household["id"],
        "property_id": str(property_record.id),
        "property_type_id": str(property_type.id),
        "active_status_id": str(active.id),
        "sold_status_id": str(sold.id),
        **{item.code: str(item.id) for item in event_types},
    }


async def create_event(
    client: AsyncClient,
    setup: dict[str, str],
    code: str,
    effective_at: datetime,
    *,
    classification: str = "OBSERVED",
    amount: int | None = None,
    payload: dict[str, object] | None = None,
    is_enabled: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/households/{setup['household_id']}/events",
        json={
            "event_type_id": setup[code],
            "idempotency_key": idempotency_key,
            "effective_at": effective_at.isoformat(),
            "property_id": setup["property_id"],
            "classification": classification,
            "amount": amount,
            "payload": payload or {},
            "is_enabled": is_enabled,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_baseline_resolution_applies_backdated_events_in_deterministic_order(
    client: AsyncClient, timeline_setup: dict[str, str]
) -> None:
    newer = await create_event(
        client,
        timeline_setup,
        "PROPERTY_VALUED",
        datetime(2023, 1, 1, 10, tzinfo=UTC),
        amount=600000,
    )
    older = await create_event(
        client,
        timeline_setup,
        "PROPERTY_VALUED",
        datetime(2021, 1, 1, 10, tzinfo=UTC),
        amount=500000,
    )
    response = await client.get(
        f"/api/v1/properties/{timeline_setup['property_id']}/state",
        params={"as_of": "2023-12-31"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["property_value"] == "600000.00"
    assert body["applied_event_ids"] == [older["id"], newer["id"]]
    assert body["baseline_date"] == "2020-01-01"


async def test_same_day_priority_and_disabled_planned_events(
    client: AsyncClient, timeline_setup: dict[str, str]
) -> None:
    moment = datetime(2025, 6, 1, 12, tzinfo=UTC)
    valued = await create_event(client, timeline_setup, "PROPERTY_VALUED", moment, amount=700000)
    sold = await create_event(client, timeline_setup, "PROPERTY_SOLD", moment, amount=710000)
    disabled = await create_event(
        client,
        timeline_setup,
        "PROPERTY_VALUED",
        datetime(2025, 6, 2, 12, tzinfo=UTC),
        classification="PLANNED",
        amount=999999,
        is_enabled=False,
    )
    timeline = await client.get(f"/api/v1/households/{timeline_setup['household_id']}/timeline")
    ids = [event["id"] for event in timeline.json()["events"]]
    assert ids.index(valued["id"]) < ids.index(sold["id"])
    assert disabled["id"] not in ids
    state = await client.get(
        f"/api/v1/properties/{timeline_setup['property_id']}/state",
        params={"as_of": "2025-12-31"},
    )
    assert state.json()["property_value"] == "710000.00"
    assert state.json()["is_active_asset"] is False


async def test_planned_event_can_be_toggled_but_observed_event_cannot(
    client: AsyncClient, timeline_setup: dict[str, str]
) -> None:
    planned = await create_event(
        client,
        timeline_setup,
        "CUSTOM_EVENT",
        datetime.now(UTC) + timedelta(days=30),
        classification="PLANNED",
    )
    toggled = await client.patch(
        f"/api/v1/events/{planned['id']}/enabled", json={"is_enabled": False}
    )
    assert toggled.status_code == 200
    assert toggled.json()["is_enabled"] is False
    moved_at = datetime.now(UTC) + timedelta(days=60)
    moved = await client.patch(
        f"/api/v1/events/{planned['id']}",
        json={"effective_at": moved_at.isoformat(), "notes": "Moved plan"},
    )
    assert moved.status_code == 200
    assert moved.json()["notes"] == "Moved plan"
    observed = await create_event(
        client, timeline_setup, "CUSTOM_EVENT", datetime.now(UTC) - timedelta(days=1)
    )
    rejected = await client.patch(
        f"/api/v1/events/{observed['id']}/enabled", json={"is_enabled": False}
    )
    assert rejected.status_code == 422
    edit_rejected = await client.patch(
        f"/api/v1/events/{observed['id']}",
        json={"effective_at": moved_at.isoformat()},
    )
    assert edit_rejected.status_code == 422


async def test_future_observed_event_has_data_quality_flag(
    client: AsyncClient, timeline_setup: dict[str, str]
) -> None:
    event = await create_event(
        client,
        timeline_setup,
        "PROPERTY_VALUED",
        datetime.now(UTC) + timedelta(days=30),
        amount=800000,
    )
    assert "OBSERVED_EVENT_IN_FUTURE" in event["data_quality_flags"]


async def test_duplicate_idempotency_key_is_rejected(
    client: AsyncClient, timeline_setup: dict[str, str]
) -> None:
    moment = datetime.now(UTC)
    await create_event(
        client,
        timeline_setup,
        "CUSTOM_EVENT",
        moment,
        idempotency_key="import-row-42",
    )
    duplicate = await client.post(
        f"/api/v1/households/{timeline_setup['household_id']}/events",
        json={
            "event_type_id": timeline_setup["CUSTOM_EVENT"],
            "idempotency_key": "import-row-42",
            "effective_at": moment.isoformat(),
            "classification": "OBSERVED",
        },
    )
    assert duplicate.status_code == 409


async def test_cross_household_event_reference_and_access_are_hidden(
    client: AsyncClient, session: AsyncSession, timeline_setup: dict[str, str]
) -> None:
    other = Household(display_name="Other", currency="EUR")
    session.add(other)
    await session.flush()
    hidden_property = Property(
        household_id=other.id,
        display_name="Hidden",
        property_type_id=uuid.UUID(timeline_setup["property_type_id"]),
        current_status_id=uuid.UUID(timeline_setup["active_status_id"]),
        default_currency="EUR",
    )
    session.add(hidden_property)
    await session.commit()
    response = await client.post(
        f"/api/v1/households/{timeline_setup['household_id']}/events",
        json={
            "event_type_id": timeline_setup["PROPERTY_VALUED"],
            "effective_at": datetime.now(UTC).isoformat(),
            "property_id": str(hidden_property.id),
            "classification": "OBSERVED",
            "amount": 1,
        },
    )
    assert response.status_code == 422
    state = await client.get(
        f"/api/v1/properties/{hidden_property.id}/state", params={"as_of": date.today()}
    )
    assert state.status_code == 404


async def test_viewer_cannot_create_or_toggle_events(
    client: AsyncClient, session: AsyncSession, timeline_setup: dict[str, str]
) -> None:
    planned = await create_event(
        client,
        timeline_setup,
        "CUSTOM_EVENT",
        datetime.now(UTC) + timedelta(days=30),
        classification="PLANNED",
    )
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(timeline_setup["household_id"])
        )
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()
    create_response = await client.post(
        f"/api/v1/households/{timeline_setup['household_id']}/events",
        json={
            "event_type_id": timeline_setup["CUSTOM_EVENT"],
            "effective_at": datetime.now(UTC).isoformat(),
            "classification": "PLANNED",
        },
    )
    assert create_response.status_code == 403
    toggle_response = await client.patch(
        f"/api/v1/events/{planned['id']}/enabled", json={"is_enabled": False}
    )
    assert toggle_response.status_code == 403


def test_temporal_and_quality_classification_is_explicit() -> None:
    today = date(2026, 1, 10)
    assert temporal_position(date(2026, 1, 9), today) == "HISTORICAL"
    assert temporal_position(today, today) == "CURRENT"
    assert temporal_position(date(2026, 1, 11), today) == "PROJECTED"
    flags = event_quality_flags(
        "PROPERTY_VALUED",
        classification=EventClassification.PLANNED,
        effective_date=date(2026, 1, 1),
        today=today,
        property_id_present=False,
        amount=None,
    )
    assert flags == [
        "PLANNED_OR_PROJECTED_EVENT_IN_PAST",
        "PROPERTY_REFERENCE_MISSING",
        "AMOUNT_MISSING",
    ]
