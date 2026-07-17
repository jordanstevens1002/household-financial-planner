import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.loan_schemas import LoanScheduleRead, ScheduleEntry
from app.models import FinancialEvent, InterestCalculationMethod, Loan, RepaymentFrequency

CENT = Decimal("0.01")


@dataclass
class LoanTerms:
    balance: Decimal
    annual_rate: Decimal
    repayment: Decimal | None
    offset: Decimal
    interest_only: bool
    term_months: int | None
    closed: bool = False
    closed_date: date | None = None


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def payments_per_year(frequency: RepaymentFrequency) -> int:
    return {
        RepaymentFrequency.WEEKLY: 52,
        RepaymentFrequency.FORTNIGHTLY: 26,
        RepaymentFrequency.MONTHLY: 12,
    }[frequency]


def add_payment_period(value: date, frequency: RepaymentFrequency) -> date:
    if frequency == RepaymentFrequency.WEEKLY:
        return value + timedelta(days=7)
    if frequency == RepaymentFrequency.FORTNIGHTLY:
        return value + timedelta(days=14)
    month_index = value.month
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def minimum_repayment(
    balance: Decimal,
    annual_rate: Decimal,
    periods: int,
    frequency: RepaymentFrequency,
) -> Decimal:
    if periods <= 0:
        return balance
    rate = annual_rate / Decimal("100") / payments_per_year(frequency)
    if rate == 0:
        return money(balance / periods)
    factor = (Decimal("1") + rate) ** periods
    return money(balance * rate * factor / (factor - Decimal("1")))


def apply_loan_event(terms: LoanTerms, event: FinancialEvent, code: str) -> None:
    if code == "LOAN_RATE_CHANGED" and event.percentage is not None:
        terms.annual_rate = event.percentage
    elif code == "LOAN_REPAYMENT_CHANGED" and event.amount is not None:
        terms.repayment = event.amount
    elif code == "LOAN_LUMP_SUM_PAID" and event.amount is not None:
        terms.balance = max(Decimal("0"), terms.balance - event.amount)
    elif code == "LOAN_OFFSET_CHANGED" and event.amount is not None:
        terms.offset = max(Decimal("0"), event.amount)
    elif code == "LOAN_REDRAWN" and event.amount is not None:
        terms.balance += event.amount
    elif code == "LOAN_TERM_CHANGED":
        raw_term = event.payload.get("term_months")
        if isinstance(raw_term, int) and raw_term > 0:
            terms.term_months = raw_term
    elif code == "LOAN_INTEREST_ONLY_STARTED":
        terms.interest_only = True
    elif code == "LOAN_INTEREST_ONLY_ENDED":
        terms.interest_only = False
    elif code in {"LOAN_REFINANCED", "LOAN_CLOSED"}:
        terms.balance = Decimal("0")
        terms.closed = True
        terms.closed_date = event.effective_at.date()


def generate_schedule(
    loan: Loan,
    typed_events: list[tuple[FinancialEvent, str]],
    through_date: date | None = None,
) -> LoanScheduleRead:
    terms = LoanTerms(
        balance=loan.opening_balance,
        annual_rate=loan.initial_interest_rate,
        repayment=loan.scheduled_repayment,
        offset=Decimal("0"),
        interest_only=loan.is_interest_only,
        term_months=loan.term_months,
    )
    per_year = payments_per_year(loan.repayment_frequency)
    periods = max(1, ((loan.term_months or 360) * per_year + 11) // 12)
    payment_date = add_payment_period(loan.opening_balance_date, loan.repayment_frequency)
    previous_date = loan.opening_balance_date
    event_index = 0
    entries: list[ScheduleEntry] = []
    total_interest = Decimal("0")
    total_repayments = Decimal("0")
    flags: list[str] = []
    payment_number = 1
    while payment_number <= periods:
        if through_date is not None and payment_date > through_date:
            break
        accrued_daily_interest = Decimal("0")
        accrual_cursor = previous_date
        while (
            event_index < len(typed_events)
            and typed_events[event_index][0].effective_at.date() <= payment_date
        ):
            event, code = typed_events[event_index]
            if loan.interest_calculation_method == InterestCalculationMethod.DAILY:
                event_date = max(previous_date, event.effective_at.date())
                days = (event_date - accrual_cursor).days
                interest_basis = max(Decimal("0"), terms.balance - terms.offset)
                accrued_daily_interest += (
                    interest_basis
                    * terms.annual_rate
                    / Decimal("100")
                    * Decimal(days)
                    / Decimal("365")
                )
                accrual_cursor = event_date
            apply_loan_event(terms, event, code)
            event_index += 1
        if terms.term_months is not None:
            periods = max(
                payment_number,
                (terms.term_months * per_year + 11) // 12,
            )
        if terms.balance <= 0 or terms.closed:
            break
        opening = terms.balance
        interest_basis = max(Decimal("0"), opening - terms.offset)
        if loan.interest_calculation_method == InterestCalculationMethod.DAILY:
            accrued_daily_interest += (
                interest_basis
                * terms.annual_rate
                / Decimal("100")
                * Decimal((payment_date - accrual_cursor).days)
                / Decimal("365")
            )
            interest = money(accrued_daily_interest)
        else:
            rate = terms.annual_rate / Decimal("100") / Decimal(per_year)
            interest = money(interest_basis * rate)
        remaining_periods = periods - payment_number + 1
        calculated = minimum_repayment(
            opening, terms.annual_rate, remaining_periods, loan.repayment_frequency
        )
        repayment = interest if terms.interest_only else (terms.repayment or calculated)
        repayment = money(min(opening + interest, repayment))
        principal = money(max(Decimal("0"), repayment - interest))
        terms.balance = money(max(Decimal("0"), opening - principal))
        entries.append(
            ScheduleEntry(
                payment_number=payment_number,
                payment_date=payment_date,
                opening_balance=money(opening),
                interest=interest,
                repayment=repayment,
                principal=principal,
                offset_balance=money(terms.offset),
                closing_balance=terms.balance,
                annual_interest_rate=terms.annual_rate,
            )
        )
        total_interest += interest
        total_repayments += repayment
        previous_date = payment_date
        payment_date = add_payment_period(payment_date, loan.repayment_frequency)
        payment_number += 1
    if terms.balance > 0 and len(entries) == periods:
        flags.append("BALANCE_REMAINS_AFTER_TERM")
    return LoanScheduleRead(
        loan_id=loan.id,
        entries=entries,
        total_interest=money(total_interest),
        total_repayments=money(total_repayments),
        payoff_date=(
            terms.closed_date
            if terms.closed_date is not None
            else entries[-1].payment_date
            if entries and terms.balance == 0
            else None
        ),
        remaining_balance=money(terms.balance),
        data_quality_flags=flags,
    )
