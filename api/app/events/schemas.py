"""Financial event API schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import EventClassification


class FinancialEventCreate(BaseModel):
    event_type_id: uuid.UUID
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    effective_at: datetime
    property_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    loan_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    percentage: Decimal | None = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=4)
    payload: dict[str, object] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)
    classification: EventClassification
    is_enabled: bool = True

    @model_validator(mode="after")
    def observed_events_cannot_be_disabled(self) -> FinancialEventCreate:
        if self.classification == EventClassification.OBSERVED and not self.is_enabled:
            raise ValueError("observed events cannot be disabled")
        return self


class FinancialEventRead(FinancialEventCreate):
    id: uuid.UUID
    household_id: uuid.UUID
    event_type_code: str
    event_priority: int
    recorded_at: datetime
    data_quality_flags: list[str]
    created_by_user_id: uuid.UUID


class EventToggle(BaseModel):
    is_enabled: bool


class PlannedEventUpdate(BaseModel):
    effective_at: datetime
    notes: str | None = Field(default=None, max_length=2000)


class EventTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    display_name: str
    priority: int
    is_active: bool


class TimelineRead(BaseModel):
    household_id: uuid.UUID
    events: list[FinancialEventRead]
    data_quality_flags: list[str]


class TemporalPosition(StrEnum):
    HISTORICAL = "HISTORICAL"
    CURRENT = "CURRENT"
    PROJECTED = "PROJECTED"


class ResolvedPropertyState(BaseModel):
    property_id: uuid.UUID
    as_of: date
    temporal_position: TemporalPosition
    baseline_id: uuid.UUID | None
    baseline_date: date | None
    property_value: Decimal | None
    loan_balance_total: Decimal | None
    status_id: uuid.UUID
    is_active_asset: bool | None
    applied_event_ids: list[uuid.UUID]
    data_quality_flags: list[str]
