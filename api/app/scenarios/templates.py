"""Country-neutral scenario template library."""

from dataclasses import dataclass
from decimal import Decimal

from app.scenarios.schemas import OverrideOperation


@dataclass(frozen=True)
class ScenarioTemplate:
    code: str
    display_name: str
    description: str
    target_entity_type: str
    override_key: str
    operation: OverrideOperation
    default_value: str


TEMPLATES = (
    ScenarioTemplate(
        "HIGHER_INTEREST_RATES",
        "Higher interest rates",
        "Increase the selected interest-rate metric.",
        "METRIC",
        "loan_interest_rate",
        "ADD",
        "1",
    ),
    ScenarioTemplate(
        "LOWER_INCOME",
        "Lower income",
        "Reduce annual net income by a percentage.",
        "METRIC",
        "annual_net_income",
        "MULTIPLY_PERCENT",
        "-10",
    ),
    ScenarioTemplate(
        "HIGHER_EXPENSES",
        "Higher household expenses",
        "Increase annual household expenses by a percentage.",
        "METRIC",
        "annual_expenses",
        "MULTIPLY_PERCENT",
        "10",
    ),
    ScenarioTemplate(
        "LOWER_PROPERTY_GROWTH",
        "Lower property growth",
        "Reduce a property-growth metric.",
        "METRIC",
        "property_growth_rate",
        "ADD",
        "-1",
    ),
    ScenarioTemplate(
        "HIGHER_PROPERTY_GROWTH",
        "Higher property growth",
        "Increase a property-growth metric.",
        "METRIC",
        "property_growth_rate",
        "ADD",
        "1",
    ),
    ScenarioTemplate(
        "DELAYED_PROPERTY_PURCHASE",
        "Delayed property purchase",
        "Move a planned property-purchase event later.",
        "FINANCIAL_EVENT",
        "effective_at",
        "SHIFT_DAYS",
        "90",
    ),
    ScenarioTemplate(
        "EARLIER_PROPERTY_PURCHASE",
        "Earlier property purchase",
        "Move a planned property-purchase event earlier.",
        "FINANCIAL_EVENT",
        "effective_at",
        "SHIFT_DAYS",
        "-90",
    ),
    ScenarioTemplate(
        "PROPERTY_VACANT",
        "Property vacant for a period",
        "Set rental income to zero for a dated period.",
        "METRIC",
        "rental_income",
        "SET",
        "0",
    ),
    ScenarioTemplate(
        "MAJOR_MAINTENANCE_COST",
        "Major maintenance cost",
        "Add a one-off planning amount to household expenses.",
        "METRIC",
        "annual_expenses",
        "ADD",
        "10000",
    ),
    ScenarioTemplate(
        "RETIREMENT_CONTRIBUTION_CHANGE",
        "Retirement contribution change",
        "Change the retirement-contribution metric by a percentage.",
        "METRIC",
        "retirement_contributions",
        "MULTIPLY_PERCENT",
        "10",
    ),
    ScenarioTemplate(
        "CUSTOM",
        "Custom",
        "Create a scenario with custom overrides.",
        "METRIC",
        "custom_metric",
        "SET",
        "0",
    ),
)

TEMPLATE_BY_CODE = {item.code: item for item in TEMPLATES}


TEMPLATE_VALUE_RULES: dict[str, tuple[Decimal, Decimal, int]] = {
    "HIGHER_INTEREST_RATES": (Decimal("0"), Decimal("100"), 4),
    "LOWER_INCOME": (Decimal("-100"), Decimal("0"), 4),
    "HIGHER_EXPENSES": (Decimal("0"), Decimal("1000"), 4),
    "LOWER_PROPERTY_GROWTH": (Decimal("-100"), Decimal("0"), 4),
    "HIGHER_PROPERTY_GROWTH": (Decimal("0"), Decimal("100"), 4),
    "DELAYED_PROPERTY_PURCHASE": (Decimal("0"), Decimal("3650"), 0),
    "EARLIER_PROPERTY_PURCHASE": (Decimal("-3650"), Decimal("0"), 0),
    "PROPERTY_VACANT": (Decimal("0"), Decimal("0"), 2),
    "MAJOR_MAINTENANCE_COST": (
        Decimal("0"),
        Decimal("9999999999999999.99"),
        2,
    ),
    "RETIREMENT_CONTRIBUTION_CHANGE": (Decimal("-100"), Decimal("1000"), 4),
}


def validate_template_value(template_code: str, value: Decimal) -> None:
    """Reject unsafe or semantically contradictory built-in template values."""
    rule = TEMPLATE_VALUE_RULES.get(template_code)
    if rule is None:
        raise ValueError("Template does not accept a configurable value")
    minimum, maximum, decimal_places = rule
    if not value.is_finite() or value < minimum or value > maximum:
        raise ValueError(f"Template value must be from {minimum} to {maximum}")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("Template value must be finite")
    actual_places = max(0, -exponent)
    if actual_places > decimal_places:
        precision = "a whole number"
        if decimal_places:
            precision = f"at most {decimal_places} decimals"
        raise ValueError(f"Template value requires {precision}")
