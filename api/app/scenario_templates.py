from dataclasses import dataclass

from app.scenario_schemas import OverrideOperation


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
