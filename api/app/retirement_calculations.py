import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.retirement_schemas import RetirementProjectionEntry

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def add_month(value: date) -> date:
    year = value.year + value.month // 12
    month = value.month % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class ContributionTerms:
    effective_from: date
    effective_to: date | None
    employer_rate: Decimal | None
    employer_amount: Decimal | None
    voluntary_pre_tax_amount: Decimal
    voluntary_post_tax_amount: Decimal
    contribution_tax_rate: Decimal
    annual_pre_tax_cap: Decimal | None
    annual_post_tax_cap: Decimal | None = None


def project_retirement(
    opening_balance: Decimal,
    opening_date: date,
    projection_date: date,
    annual_return_rate: Decimal,
    annual_fees: Decimal,
    annual_salary: Decimal,
    profiles: list[ContributionTerms],
    adjustments: list[tuple[date, Decimal]],
) -> tuple[list[RetirementProjectionEntry], list[str]]:
    if projection_date < opening_date:
        raise ValueError("projection_date must not precede opening_balance_date")
    if (
        projection_date.year - opening_date.year
    ) * 12 + projection_date.month - opening_date.month > 960:
        raise ValueError("projection period cannot exceed 80 years")
    balance = money(opening_balance)
    cursor = opening_date
    entries: list[RetirementProjectionEntry] = []
    warnings: list[str] = []
    cap_warning_years: set[int] = set()
    while cursor < projection_date:
        period_end = min(add_month(cursor), projection_date)
        profile = next(
            (
                item
                for item in reversed(profiles)
                if item.effective_from <= period_end
                and (item.effective_to is None or item.effective_to >= period_end)
            ),
            None,
        )
        employer = voluntary_pre_tax = voluntary_post_tax = contribution_tax = Decimal("0")
        if profile is not None:
            annual_employer = profile.employer_amount or (
                annual_salary * (profile.employer_rate or Decimal("0")) / Decimal("100")
            )
            employer = money(annual_employer / Decimal("12"))
            voluntary_pre_tax = money(profile.voluntary_pre_tax_amount / Decimal("12"))
            voluntary_post_tax = money(profile.voluntary_post_tax_amount / Decimal("12"))
            contribution_tax = money(
                (employer + voluntary_pre_tax) * profile.contribution_tax_rate / Decimal("100")
            )
            if (
                profile.annual_pre_tax_cap is not None
                and annual_employer + profile.voluntary_pre_tax_amount > profile.annual_pre_tax_cap
                and period_end.year not in cap_warning_years
            ):
                warnings.append(
                    f"Pre-tax contributions exceed the configured annual cap in {period_end.year}."
                )
                cap_warning_years.add(period_end.year)
            if (
                profile.annual_post_tax_cap is not None
                and profile.voluntary_post_tax_amount > profile.annual_post_tax_cap
                and -period_end.year not in cap_warning_years
            ):
                warnings.append(
                    f"Post-tax contributions exceed the configured annual cap in {period_end.year}."
                )
                cap_warning_years.add(-period_end.year)
        adjustment = money(
            sum(
                (amount for event_date, amount in adjustments if cursor < event_date <= period_end),
                Decimal("0"),
            )
        )
        opening = balance
        fees = money(annual_fees / Decimal("12"))
        contribution_net = employer + voluntary_pre_tax + voluntary_post_tax - contribution_tax
        earnings = money(
            max(Decimal("0"), opening + contribution_net + adjustment)
            * annual_return_rate
            / Decimal("100")
            / Decimal("12")
        )
        balance = money(
            max(Decimal("0"), opening + contribution_net + adjustment + earnings - fees)
        )
        entries.append(
            RetirementProjectionEntry(
                projection_date=period_end,
                opening_balance=opening,
                employer_contributions=employer,
                voluntary_pre_tax_contributions=voluntary_pre_tax,
                voluntary_post_tax_contributions=voluntary_post_tax,
                contribution_tax=contribution_tax,
                fees=fees,
                earnings=earnings,
                balance_adjustments=adjustment,
                closing_balance=balance,
            )
        )
        cursor = period_end
    return entries, warnings
