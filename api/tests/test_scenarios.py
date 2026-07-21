import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from time import perf_counter

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApplicationUser,
    EventClassification,
    EventType,
    FinancialEvent,
    Household,
    HouseholdMembership,
    HouseholdRole,
    Scenario,
    ScenarioOverride,
)
from app.scenario_calculations import calculate_scenario
from tests.test_households import create_household


def override(
    key: str,
    operation: str,
    value: str,
    *,
    effective_from: date = date(2026, 1, 1),
    effective_to: date | None = None,
) -> ScenarioOverride:
    return ScenarioOverride(
        id=uuid.uuid4(),
        scenario_id=uuid.uuid4(),
        target_entity_type="METRIC",
        target_entity_id=None,
        effective_from=effective_from,
        effective_to=effective_to,
        override_key=key,
        operation=operation,
        value_json={"value": value},
    )


def test_calculation_applies_operations_dates_and_selected_metrics() -> None:
    values, applied, _, assumptions, warnings = calculate_scenario(
        {"income": Decimal("100"), "expenses": Decimal("40")},
        [
            override("income", "MULTIPLY_PERCENT", "-10"),
            override("expenses", "ADD", "5"),
            override("new_metric", "SET", "12"),
            override("income", "SET", "1", effective_from=date(2028, 1, 1)),
            override("expenses", "SET", "1", effective_to=date(2025, 12, 31)),
        ],
        date(2027, 1, 1),
        ["income", "expenses", "missing"],
    )
    assert values == {"income": Decimal("90"), "expenses": Decimal("45")}
    assert len(applied) == 3
    assert len(assumptions) == 3
    assert warnings == ["Selected metric not present: missing"]


def test_calculation_reports_invalid_or_unsupported_overrides() -> None:
    bad_value = override("income", "ADD", "not-a-number")
    absent = override("missing", "ADD", "1")
    unsupported = override("income", "ENABLE", "1")
    values, applied, _, _, warnings = calculate_scenario(
        {"income": Decimal("100")}, [bad_value, absent, unsupported], date(2027, 1, 1), []
    )
    assert values == {"income": Decimal("100")}
    assert applied == []
    assert len(warnings) == 3


async def test_custom_template_inheritance_and_comparison(client: AsyncClient) -> None:
    household = await create_household(client)
    templates = await client.get("/api/v1/scenario-templates")
    assert templates.status_code == 200
    assert all("AUSTRALIA" not in item["code"] for item in templates.json())

    base = await client.post(
        f"/api/v1/households/{household['id']}/scenarios",
        json={
            "display_name": "A little less income",
            "overrides": [
                {
                    "target_entity_type": "METRIC",
                    "effective_from": "2026-01-01",
                    "override_key": "annual_net_income",
                    "operation": "MULTIPLY_PERCENT",
                    "value_json": {"value": "-10"},
                }
            ],
        },
    )
    assert base.status_code == 201, base.text
    child = await client.post(
        f"/api/v1/households/{household['id']}/scenarios",
        json={
            "display_name": "And higher expenses",
            "base_scenario_id": base.json()["id"],
            "overrides": [
                {
                    "target_entity_type": "METRIC",
                    "effective_from": "2026-01-01",
                    "override_key": "annual_expenses",
                    "operation": "MULTIPLY_PERCENT",
                    "value_json": {"value": "20"},
                }
            ],
        },
    )
    assert child.status_code == 201, child.text
    calculation = await client.post(
        f"/api/v1/scenarios/{child.json()['id']}/calculate",
        json={
            "as_of": "2027-01-01",
            "baseline_metrics": {"annual_net_income": "100000", "annual_expenses": "50000"},
            "selected_metrics": ["annual_net_income", "annual_expenses"],
        },
    )
    assert calculation.status_code == 200, calculation.text
    assert calculation.json()["metrics"] == {
        "annual_net_income": "90000.0",
        "annual_expenses": "60000.0",
    }
    compared = await client.post(
        "/api/v1/scenarios/compare",
        json={
            "scenario_ids": [base.json()["id"], child.json()["id"]],
            "as_of": "2027-01-01",
            "baseline_metrics": {"annual_net_income": "100000", "annual_expenses": "50000"},
        },
    )
    assert compared.status_code == 200, compared.text
    assert len(compared.json()["scenarios"]) == 2


async def test_template_value_zero_is_respected(client: AsyncClient) -> None:
    household = await create_household(client)
    response = await client.post(
        f"/api/v1/households/{household['id']}/scenarios/from-template",
        json={
            "display_name": "No income change",
            "template_code": "LOWER_INCOME",
            "effective_from": "2026-01-01",
            "value": 0,
        },
    )
    assert response.status_code == 201, response.text
    calculation = await client.post(
        f"/api/v1/scenarios/{response.json()['id']}/calculate",
        json={"as_of": "2027-01-01", "baseline_metrics": {"annual_net_income": 100}},
    )
    assert calculation.json()["metrics"]["annual_net_income"] == "100"


async def test_event_override_is_non_mutating_and_household_scoped(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    event_type = EventType(code="SCENARIO_TEST", display_name="Test", priority=10)
    session.add(event_type)
    await session.flush()
    user_id = (await client.get("/api/v1/me")).json()["id"]
    event = FinancialEvent(
        household_id=uuid.UUID(household["id"]),
        event_type_id=event_type.id,
        effective_at=datetime(2027, 1, 1, tzinfo=UTC),
        payload={},
        classification=EventClassification.PLANNED,
        is_enabled=True,
        data_quality_flags=[],
        created_by_user_id=uuid.UUID(user_id),
    )
    other = Household(display_name="Other", currency="NZD")
    session.add_all([event, other])
    await session.commit()
    scenario = await client.post(
        f"/api/v1/households/{household['id']}/scenarios",
        json={"display_name": "Delay an event"},
    )
    added = await client.post(
        f"/api/v1/scenarios/{scenario.json()['id']}/overrides",
        json={
            "target_entity_type": "FINANCIAL_EVENT",
            "target_entity_id": str(event.id),
            "effective_from": "2026-01-01",
            "override_key": "effective_at",
            "operation": "SHIFT_DAYS",
            "value_json": {"value": 30},
        },
    )
    assert added.status_code == 201, added.text
    calculated = await client.post(
        f"/api/v1/scenarios/{scenario.json()['id']}/calculate",
        json={"as_of": "2027-01-01", "baseline_metrics": {}},
    )
    assert calculated.json()["event_overrides"][0]["target_entity_id"] == str(event.id)
    await session.refresh(event)
    assert event.effective_at.date() == date(2027, 1, 1)

    cross_event = FinancialEvent(
        household_id=other.id,
        event_type_id=event_type.id,
        effective_at=datetime(2027, 1, 1, tzinfo=UTC),
        payload={},
        classification=EventClassification.PLANNED,
        is_enabled=True,
        data_quality_flags=[],
        created_by_user_id=uuid.UUID(user_id),
    )
    session.add(cross_event)
    await session.commit()
    rejected = await client.post(
        f"/api/v1/scenarios/{scenario.json()['id']}/overrides",
        json={
            "target_entity_type": "FINANCIAL_EVENT",
            "target_entity_id": str(cross_event.id),
            "effective_from": "2026-01-01",
            "override_key": "is_enabled",
            "operation": "DISABLE",
        },
    )
    assert rejected.status_code == 422


async def test_scenario_access_roles_and_cross_household_bases(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    user = await session.scalar(
        select(ApplicationUser).where(ApplicationUser.oidc_subject == "test-user")
    )
    assert user is not None
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(household["id"]),
            HouseholdMembership.application_user_id == user.id,
        )
    )
    assert membership is not None
    other = Household(display_name="Private", currency="USD")
    session.add(other)
    await session.flush()
    hidden = Scenario(household_id=other.id, display_name="Hidden", is_active=True)
    session.add(hidden)
    await session.commit()

    cross_base = await client.post(
        f"/api/v1/households/{household['id']}/scenarios",
        json={"display_name": "Invalid base", "base_scenario_id": str(hidden.id)},
    )
    assert cross_base.status_code == 422
    hidden_calculation = await client.post(
        f"/api/v1/scenarios/{hidden.id}/calculate",
        json={"as_of": "2027-01-01", "baseline_metrics": {}},
    )
    assert hidden_calculation.status_code == 404

    membership.role = HouseholdRole.VIEWER
    await session.commit()
    forbidden = await client.post(
        f"/api/v1/households/{household['id']}/scenarios",
        json={"display_name": "Cannot edit"},
    )
    assert forbidden.status_code == 403


def test_scenario_calculation_performance() -> None:
    overrides = [override("income", "ADD", "1") for _ in range(1000)]
    samples: list[float] = []
    for _ in range(100):
        started = perf_counter()
        result = calculate_scenario({"income": Decimal("0")}, overrides, date(2027, 1, 1), [])
        samples.append((perf_counter() - started) * 1000)
    samples.sort()
    assert result[0]["income"] == Decimal("1000")
    assert samples[94] < 100
