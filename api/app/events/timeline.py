"""Timeline resolution calculations."""

from datetime import date
from decimal import Decimal

from app.events.schemas import TemporalPosition
from app.models import EventClassification, FinancialEvent


def temporal_position(as_of: date, today: date) -> TemporalPosition:
    if as_of < today:
        return TemporalPosition.HISTORICAL
    if as_of > today:
        return TemporalPosition.PROJECTED
    return TemporalPosition.CURRENT


def event_quality_flags(
    event_type_code: str,
    classification: EventClassification,
    effective_date: date,
    today: date,
    property_id_present: bool,
    amount: Decimal | None,
) -> list[str]:
    flags: list[str] = []
    if classification == EventClassification.OBSERVED and effective_date > today:
        flags.append("OBSERVED_EVENT_IN_FUTURE")
    if classification != EventClassification.OBSERVED and effective_date < today:
        flags.append("PLANNED_OR_PROJECTED_EVENT_IN_PAST")
    if event_type_code.startswith("PROPERTY_") and not property_id_present:
        flags.append("PROPERTY_REFERENCE_MISSING")
    if event_type_code in {"PROPERTY_VALUED", "PROPERTY_SOLD"} and amount is None:
        flags.append("AMOUNT_MISSING")
    return flags


def apply_property_event(
    event: FinancialEvent,
    event_type_code: str,
    state: dict[str, object],
) -> None:
    if event_type_code in {"PROPERTY_VALUED", "PROPERTY_SOLD"} and event.amount is not None:
        state["property_value"] = event.amount
    if event_type_code == "PROPERTY_STATUS_CHANGED":
        status_id = event.payload.get("status_id")
        if isinstance(status_id, str):
            state["status_id"] = status_id
    if event_type_code in {"PROPERTY_SOLD", "PROPERTY_TRANSFERRED"}:
        state["is_active_asset"] = False
