from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.models import PaymentFrequency

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
DAYS = Decimal("365")

ANNUAL_MULTIPLIERS = {
    PaymentFrequency.WEEKLY: Decimal("52"),
    PaymentFrequency.FORTNIGHTLY: Decimal("26"),
    PaymentFrequency.MONTHLY: Decimal("12"),
    PaymentFrequency.QUARTERLY: Decimal("4"),
    PaymentFrequency.ANNUAL: Decimal("1"),
}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def daily_amount(amount: Decimal, frequency: PaymentFrequency) -> Decimal:
    if frequency == PaymentFrequency.ONCE:
        raise ValueError("one-off values do not have a daily rate")
    return amount * ANNUAL_MULTIPLIERS[frequency] / DAYS


def inclusive_dates(from_date: date, to_date: date) -> list[date]:
    if to_date < from_date:
        raise ValueError("to_date must not precede from_date")
    return [from_date + timedelta(days=offset) for offset in range((to_date - from_date).days + 1)]
