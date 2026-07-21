import statistics
import time
from datetime import date
from decimal import Decimal

from app.retirement_calculations import ContributionTerms, project_retirement


def run_once() -> float:
    profile = ContributionTerms(
        effective_from=date(2025, 1, 1),
        effective_to=None,
        employer_rate=Decimal("12"),
        employer_amount=None,
        voluntary_concessional_amount=Decimal("5000"),
        non_concessional_amount=Decimal("2000"),
        contribution_tax_rate=Decimal("15"),
        annual_cap=Decimal("30000"),
        non_concessional_cap=Decimal("120000"),
    )
    started = time.perf_counter()
    entries, _ = project_retirement(
        Decimal("100000"),
        date(2025, 1, 1),
        date(2065, 1, 1),
        Decimal("6"),
        Decimal("300"),
        Decimal("100000"),
        [profile],
        [(date(2030, 6, 1), Decimal("10000"))],
    )
    assert len(entries) == 480
    return (time.perf_counter() - started) * 1000


for _ in range(10):
    run_once()
durations = [run_once() for _ in range(100)]
p95 = statistics.quantiles(durations, n=100, method="inclusive")[94]
print(f"Requests: {len(durations)}")
print(f"p50: {statistics.median(durations):.2f} ms")
print(f"p95: {p95:.2f} ms")
print(f"maximum: {max(durations):.2f} ms")
print("Threshold: p95 < 300 ms")
print("Result: PASS" if p95 < 300 else "Result: FAIL")
