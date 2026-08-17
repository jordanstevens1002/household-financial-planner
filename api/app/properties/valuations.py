"""Shared ordering and provenance rules for property valuations."""

from sqlalchemy import case
from sqlalchemy.sql.elements import ColumnElement

from app.models import PropertyValuation, ValuationType

VALUATION_ESTIMATE_BY_TYPE = {
    ValuationType.PURCHASE_PRICE: False,
    ValuationType.USER_ESTIMATE: True,
    ValuationType.FORMAL_VALUATION: False,
    ValuationType.AGENT_APPRAISAL: True,
    ValuationType.AUTOMATED_ESTIMATE: True,
    ValuationType.SALE_PRICE: False,
    ValuationType.SCENARIO_VALUE: True,
}

VALUATION_PRIORITY = {
    ValuationType.USER_ESTIMATE: 1,
    ValuationType.AUTOMATED_ESTIMATE: 2,
    ValuationType.AGENT_APPRAISAL: 3,
    ValuationType.FORMAL_VALUATION: 4,
    ValuationType.PURCHASE_PRICE: 5,
    ValuationType.SALE_PRICE: 6,
    ValuationType.SCENARIO_VALUE: 0,
}


def valuation_priority_expression() -> ColumnElement[int]:
    """Return deterministic source precedence for observations on the same date."""
    return case(VALUATION_PRIORITY, value=PropertyValuation.valuation_type, else_=-1)
