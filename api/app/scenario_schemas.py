import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OverrideOperation = Literal["SET", "ADD", "MULTIPLY_PERCENT", "ENABLE", "DISABLE", "SHIFT_DAYS"]


class OverrideCreate(BaseModel):
    target_entity_type: str = Field(min_length=1, max_length=80)
    target_entity_id: uuid.UUID | None = None
    effective_from: date
    effective_to: date | None = None
    override_key: str = Field(min_length=1, max_length=120)
    operation: OverrideOperation
    value_json: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_override(self) -> OverrideCreate:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        if self.operation not in {"ENABLE", "DISABLE"} and "value" not in self.value_json:
            raise ValueError("operation requires value_json.value")
        return self


class ScenarioCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    template_code: str | None = Field(default=None, max_length=80)
    base_scenario_id: uuid.UUID | None = None
    is_active: bool = True
    overrides: list[OverrideCreate] = Field(default_factory=list)


class ScenarioUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    base_scenario_id: uuid.UUID | None = None
    is_active: bool | None = None


class TemplateScenarioCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    template_code: str = Field(min_length=1, max_length=80)
    effective_from: date
    effective_to: date | None = None
    target_entity_id: uuid.UUID | None = None
    value: Decimal | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> TemplateScenarioCreate:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    household_id: uuid.UUID
    display_name: str
    description: str | None
    template_code: str | None
    base_scenario_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OverrideRead(OverrideCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    scenario_id: uuid.UUID


class ScenarioDetailRead(ScenarioRead):
    overrides: list[OverrideRead]


class TemplateRead(BaseModel):
    code: str
    display_name: str
    description: str
    target_entity_type: str
    override_key: str
    operation: str
    default_value: str


class ScenarioCalculationRequest(BaseModel):
    as_of: date
    baseline_metrics: dict[str, Decimal]
    selected_metrics: list[str] = Field(default_factory=list)


class AppliedEventOverride(BaseModel):
    target_entity_id: uuid.UUID
    override_key: str
    operation: str
    value_json: dict[str, object]


class ScenarioCalculationRead(BaseModel):
    scenario_id: uuid.UUID
    as_of: date
    metrics: dict[str, Decimal]
    applied_override_ids: list[uuid.UUID]
    event_overrides: list[AppliedEventOverride]
    assumptions_used: list[str]
    warnings: list[str]


class ScenarioCompareRequest(BaseModel):
    scenario_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    as_of: date
    baseline_metrics: dict[str, Decimal]
    selected_metrics: list[str] = Field(default_factory=list)


class ScenarioComparisonRead(BaseModel):
    as_of: date
    baseline: dict[str, Decimal]
    scenarios: list[ScenarioCalculationRead]
