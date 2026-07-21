import uuid
from collections.abc import Sequence
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import ROLE_LEVEL, current_user, require_household_role
from app.logging import get_logger
from app.models import (
    ApplicationUser,
    FinancialEvent,
    HouseholdMembership,
    HouseholdRole,
    Scenario,
    ScenarioOverride,
)
from app.scenario_calculations import calculate_scenario
from app.scenario_schemas import (
    OverrideCreate,
    OverrideRead,
    ScenarioCalculationRead,
    ScenarioCalculationRequest,
    ScenarioCompareRequest,
    ScenarioComparisonRead,
    ScenarioCreate,
    ScenarioDetailRead,
    ScenarioRead,
    ScenarioUpdate,
    TemplateRead,
    TemplateScenarioCreate,
)
from app.scenario_templates import TEMPLATE_BY_CODE, TEMPLATES

router = APIRouter(prefix="/api/v1", tags=["scenarios"])
logger = get_logger(component="scenarios")


async def _scenario_with_access(
    scenario_id: uuid.UUID,
    minimum: HouseholdRole,
    user: ApplicationUser,
    session: AsyncSession,
) -> Scenario:
    scenario = await session.scalar(
        select(Scenario)
        .join(HouseholdMembership, HouseholdMembership.household_id == Scenario.household_id)
        .where(
            Scenario.id == scenario_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    if scenario is None:
        raise HTTPException(404, "Scenario not found")
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == scenario.household_id,
            HouseholdMembership.application_user_id == user.id,
        )
    )
    assert membership is not None
    if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
        raise HTTPException(403, "Insufficient household role")
    return scenario


async def _validate_base(
    household_id: uuid.UUID,
    base_id: uuid.UUID | None,
    scenario_id: uuid.UUID | None,
    session: AsyncSession,
) -> None:
    seen = {scenario_id} if scenario_id else set()
    current = base_id
    depth = 0
    while current is not None:
        if current in seen:
            raise HTTPException(422, "Scenario inheritance cannot contain a cycle")
        seen.add(current)
        base = await session.get(Scenario, current)
        if base is None or base.household_id != household_id:
            raise HTTPException(422, "Base scenario must belong to the household")
        current = base.base_scenario_id
        depth += 1
        if depth > 10:
            raise HTTPException(422, "Scenario inheritance is limited to 10 levels")


async def _validate_override(
    household_id: uuid.UUID, payload: OverrideCreate, session: AsyncSession
) -> None:
    if payload.target_entity_type == "METRIC":
        if payload.target_entity_id is not None:
            raise HTTPException(422, "Metric overrides cannot have a target entity ID")
        if payload.operation not in {"SET", "ADD", "MULTIPLY_PERCENT"}:
            raise HTTPException(422, "Unsupported metric override operation")
        return
    if payload.target_entity_type == "FINANCIAL_EVENT":
        if payload.target_entity_id is None:
            raise HTTPException(422, "Financial event override requires a target ID")
        event = await session.get(FinancialEvent, payload.target_entity_id)
        if event is None or event.household_id != household_id:
            raise HTTPException(422, "Financial event must belong to the household")
        return
    raise HTTPException(422, "Target type must be METRIC or FINANCIAL_EVENT")


async def _overrides_for_chain(
    scenario: Scenario, session: AsyncSession
) -> Sequence[ScenarioOverride]:
    chain: list[Scenario] = []
    current: Scenario | None = scenario
    for _ in range(11):
        if current is None:
            break
        chain.append(current)
        current = (
            await session.get(Scenario, current.base_scenario_id)
            if current.base_scenario_id
            else None
        )
    chain.reverse()
    result: list[ScenarioOverride] = []
    for item in chain:
        result.extend(
            await session.scalars(
                select(ScenarioOverride)
                .where(ScenarioOverride.scenario_id == item.id)
                .order_by(ScenarioOverride.effective_from, ScenarioOverride.id)
            )
        )
    return result


async def _calculate(
    scenario: Scenario, payload: ScenarioCalculationRequest, session: AsyncSession
) -> ScenarioCalculationRead:
    values = calculate_scenario(
        payload.baseline_metrics,
        await _overrides_for_chain(scenario, session),
        payload.as_of,
        payload.selected_metrics,
    )
    return ScenarioCalculationRead(
        scenario_id=scenario.id,
        as_of=payload.as_of,
        metrics=values[0],
        applied_override_ids=values[1],
        event_overrides=values[2],
        assumptions_used=values[3],
        warnings=values[4],
    )


@router.get("/scenario-templates", response_model=list[TemplateRead])
async def list_templates(_: ApplicationUser = Depends(current_user)) -> list[TemplateRead]:
    return [TemplateRead(**asdict(template)) for template in TEMPLATES]


@router.get("/households/{household_id}/scenarios", response_model=list[ScenarioRead])
async def list_scenarios(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Scenario]:
    return list(
        await session.scalars(
            select(Scenario)
            .where(Scenario.household_id == household_id)
            .order_by(Scenario.display_name)
        )
    )


@router.post("/households/{household_id}/scenarios", response_model=ScenarioRead, status_code=201)
async def create_scenario(
    household_id: uuid.UUID,
    payload: ScenarioCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Scenario:
    if payload.template_code is not None and payload.template_code not in TEMPLATE_BY_CODE:
        raise HTTPException(422, "Unknown scenario template")
    await _validate_base(household_id, payload.base_scenario_id, None, session)
    for override in payload.overrides:
        await _validate_override(household_id, override, session)
    values = payload.model_dump(exclude={"overrides"})
    scenario = Scenario(household_id=household_id, **values)
    session.add(scenario)
    await session.flush()
    session.add_all(
        [
            ScenarioOverride(scenario_id=scenario.id, **item.model_dump())
            for item in payload.overrides
        ]
    )
    await session.commit()
    await session.refresh(scenario)
    logger.info("scenario_created", scenario_id=str(scenario.id), household_id=str(household_id))
    return scenario


@router.post(
    "/households/{household_id}/scenarios/from-template",
    response_model=ScenarioRead,
    status_code=201,
)
async def create_from_template(
    household_id: uuid.UUID,
    payload: TemplateScenarioCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Scenario:
    template = TEMPLATE_BY_CODE.get(payload.template_code)
    if template is None or template.code == "CUSTOM":
        raise HTTPException(422, "Template does not provide a default override")
    override_payload = OverrideCreate(
        target_entity_type=template.target_entity_type,
        target_entity_id=payload.target_entity_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        override_key=template.override_key,
        operation=template.operation,
        value_json={
            "value": str(payload.value if payload.value is not None else template.default_value)
        },
    )
    await _validate_override(household_id, override_payload, session)
    scenario = Scenario(
        household_id=household_id,
        display_name=payload.display_name,
        description=payload.description or template.description,
        template_code=template.code,
        is_active=True,
    )
    session.add(scenario)
    await session.flush()
    session.add(
        ScenarioOverride(
            scenario_id=scenario.id,
            **override_payload.model_dump(),
        )
    )
    await session.commit()
    await session.refresh(scenario)
    return scenario


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetailRead)
async def get_scenario(
    scenario_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ScenarioDetailRead:
    scenario = await _scenario_with_access(scenario_id, HouseholdRole.VIEWER, user, session)
    overrides = list(
        await session.scalars(
            select(ScenarioOverride)
            .where(ScenarioOverride.scenario_id == scenario.id)
            .order_by(ScenarioOverride.effective_from, ScenarioOverride.id)
        )
    )
    return ScenarioDetailRead(
        **ScenarioRead.model_validate(scenario).model_dump(),
        overrides=[OverrideRead.model_validate(item) for item in overrides],
    )


@router.put("/scenarios/{scenario_id}", response_model=ScenarioRead)
async def update_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Scenario:
    scenario = await _scenario_with_access(scenario_id, HouseholdRole.EDITOR, user, session)
    if "base_scenario_id" in payload.model_fields_set:
        await _validate_base(scenario.household_id, payload.base_scenario_id, scenario.id, session)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, key, value)
    await session.commit()
    await session.refresh(scenario)
    return scenario


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: uuid.UUID,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    scenario = await _scenario_with_access(scenario_id, HouseholdRole.EDITOR, user, session)
    await session.delete(scenario)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/scenarios/{scenario_id}/overrides", response_model=OverrideRead, status_code=201)
async def add_override(
    scenario_id: uuid.UUID,
    payload: OverrideCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ScenarioOverride:
    scenario = await _scenario_with_access(scenario_id, HouseholdRole.EDITOR, user, session)
    await _validate_override(scenario.household_id, payload, session)
    override = ScenarioOverride(scenario_id=scenario.id, **payload.model_dump())
    session.add(override)
    await session.commit()
    await session.refresh(override)
    return override


@router.post("/scenarios/{scenario_id}/calculate", response_model=ScenarioCalculationRead)
async def calculate(
    scenario_id: uuid.UUID,
    payload: ScenarioCalculationRequest,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ScenarioCalculationRead:
    scenario = await _scenario_with_access(scenario_id, HouseholdRole.VIEWER, user, session)
    return await _calculate(scenario, payload, session)


@router.post("/scenarios/compare", response_model=ScenarioComparisonRead)
async def compare(
    payload: ScenarioCompareRequest,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ScenarioComparisonRead:
    scenarios = [
        await _scenario_with_access(item, HouseholdRole.VIEWER, user, session)
        for item in payload.scenario_ids
    ]
    if len({item.household_id for item in scenarios}) != 1:
        raise HTTPException(422, "Compared scenarios must belong to one household")
    request = ScenarioCalculationRequest(
        as_of=payload.as_of,
        baseline_metrics=payload.baseline_metrics,
        selected_metrics=payload.selected_metrics,
    )
    baseline = dict(payload.baseline_metrics)
    if payload.selected_metrics:
        baseline = {key: baseline[key] for key in payload.selected_metrics if key in baseline}
    return ScenarioComparisonRead(
        as_of=payload.as_of,
        baseline=baseline,
        scenarios=[await _calculate(item, request, session) for item in scenarios],
    )
