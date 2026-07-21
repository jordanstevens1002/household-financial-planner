from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_repayment(principal: Decimal, annual_rate: Decimal, years: int) -> Decimal:
    if principal <= 0:
        return Decimal("0.00")
    periods = years * 12
    rate = annual_rate / Decimal("100") / Decimal("12")
    if rate == 0:
        return money(principal / periods)
    factor = (Decimal("1") + rate) ** periods
    return money(principal * rate * factor / (factor - Decimal("1")))


@dataclass(frozen=True)
class FeasibilityValues:
    equity_funding: Decimal
    borrowed_funding: Decimal
    additional_loan: Decimal
    total_debt: Decimal
    monthly_repayment: Decimal
    projected_monthly_surplus: Decimal
    lvr: Decimal
    funding_gap: Decimal
    required_total: Decimal
    failed_thresholds: list[str]


def calculate_feasibility(
    purchase_price: Decimal,
    total_costs: Decimal,
    desired_buffer: Decimal,
    equity_funding: Decimal,
    borrowed_funding: Decimal,
    maximum_additional_borrowing: Decimal,
    annual_interest_rate: Decimal,
    loan_term_years: int,
    current_monthly_surplus: Decimal,
    max_lvr: Decimal | None,
    minimum_monthly_surplus: Decimal | None,
) -> FeasibilityValues:
    required = money(purchase_price + total_costs + desired_buffer)
    uncovered = max(Decimal("0"), required - equity_funding - borrowed_funding)
    additional = money(min(uncovered, maximum_additional_borrowing))
    gap = money(max(Decimal("0"), uncovered - additional))
    debt = money(borrowed_funding + additional)
    repayment = monthly_repayment(debt, annual_interest_rate, loan_term_years)
    projected_surplus = money(current_monthly_surplus - repayment)
    lvr = money(debt / purchase_price * Decimal("100"))
    failed: list[str] = []
    if gap > 0:
        failed.append("funding_gap")
    if max_lvr is not None and lvr > max_lvr:
        failed.append("max_lvr")
    if minimum_monthly_surplus is not None and projected_surplus < minimum_monthly_surplus:
        failed.append("minimum_monthly_surplus")
    return FeasibilityValues(
        equity_funding=money(equity_funding),
        borrowed_funding=money(borrowed_funding),
        additional_loan=additional,
        total_debt=debt,
        monthly_repayment=repayment,
        projected_monthly_surplus=projected_surplus,
        lvr=lvr,
        funding_gap=gap,
        required_total=required,
        failed_thresholds=failed,
    )
