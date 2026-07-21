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
    voluntary_concessional_amount: Decimal
    non_concessional_amount: Decimal
    contribution_tax_rate: Decimal
    annual_cap: Decimal | None
    non_concessional_cap: Decimal | None = None


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
        employer = voluntary = non_concessional = contribution_tax = Decimal("0")
        if profile is not None:
            annual_employer = profile.employer_amount or (
                annual_salary * (profile.employer_rate or Decimal("0")) / Decimal("100")
            )
            employer = money(annual_employer / Decimal("12"))
            voluntary = money(profile.voluntary_concessional_amount / Decimal("12"))
            non_concessional = money(profile.non_concessional_amount / Decimal("12"))
            contribution_tax = money(
                (employer + voluntary) * profile.contribution_tax_rate / Decimal("100")
            )
            if (
                profile.annual_cap is not None
                and annual_employer + profile.voluntary_concessional_amount > profile.annual_cap
                and period_end.year not in cap_warning_years
            ):
                warnings.append(
                    "Concessional contributions exceed the configured annual cap "
                    f"in {period_end.year}."
                )
                cap_warning_years.add(period_end.year)
            if (
                profile.non_concessional_cap is not None
                and profile.non_concessional_amount > profile.non_concessional_cap
                and -period_end.year not in cap_warning_years
            ):
                warnings.append(
                    "Non-concessional contributions exceed the configured annual cap "
                    f"in {period_end.year}."
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
        contribution_net = employer + voluntary + non_concessional - contribution_tax
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
                voluntary_concessional_contributions=voluntary,
                non_concessional_contributions=non_concessional,
                contribution_tax=contribution_tax,
                fees=fees,
                earnings=earnings,
                balance_adjustments=adjustment,
                closing_balance=balance,
            )
        )
        cursor = period_end
    return entries, warnings
