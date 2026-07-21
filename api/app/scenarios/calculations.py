"""Scenario override calculations."""

import uuid
from collections.abc import Iterable
from datetime import date
from decimal import Decimal, InvalidOperation

from app.models import ScenarioOverride
from app.scenarios.schemas import AppliedEventOverride


def calculate_scenario(
    baseline: dict[str, Decimal],
    overrides: Iterable[ScenarioOverride],
    as_of: date,
    selected_metrics: list[str],
) -> tuple[dict[str, Decimal], list[uuid.UUID], list[AppliedEventOverride], list[str], list[str]]:
    metrics = dict(baseline)
    applied: list[uuid.UUID] = []
    event_overrides: list[AppliedEventOverride] = []
    assumptions: list[str] = []
    warnings: list[str] = []

    for override in overrides:
        if override.effective_from > as_of or (
            override.effective_to is not None and override.effective_to < as_of
        ):
            continue
        if override.target_entity_type == "FINANCIAL_EVENT":
            if override.target_entity_id is None:
                warnings.append(f"Override {override.id} has no financial event target")
                continue
            event_overrides.append(
                AppliedEventOverride(
                    target_entity_id=override.target_entity_id,
                    override_key=override.override_key,
                    operation=override.operation,
                    value_json=override.value_json,
                )
            )
            applied.append(override.id)
            assumptions.append(f"Applied {override.operation} to event {override.target_entity_id}")
            continue
        if override.target_entity_type != "METRIC":
            warnings.append(f"Unsupported target type: {override.target_entity_type}")
            continue
        try:
            value = Decimal(str(override.value_json["value"]))
        except KeyError, InvalidOperation, TypeError, ValueError:
            warnings.append(f"Override {override.id} has an invalid numeric value")
            continue
        current = metrics.get(override.override_key)
        if override.operation == "SET":
            metrics[override.override_key] = value
        elif current is None:
            warnings.append(f"Metric not present for {override.operation}: {override.override_key}")
            continue
        elif override.operation == "ADD":
            metrics[override.override_key] = current + value
        elif override.operation == "MULTIPLY_PERCENT":
            metrics[override.override_key] = current * (Decimal("1") + value / Decimal("100"))
        else:
            warnings.append(f"Unsupported metric operation: {override.operation}")
            continue
        applied.append(override.id)
        assumptions.append(
            f"Applied {override.operation} {value} to metric {override.override_key}"
        )

    if selected_metrics:
        missing = [key for key in selected_metrics if key not in metrics]
        warnings.extend(f"Selected metric not present: {key}" for key in missing)
        metrics = {key: metrics[key] for key in selected_metrics if key in metrics}
    return metrics, applied, event_overrides, assumptions, warnings
