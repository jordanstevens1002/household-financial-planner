import statistics
import time
from decimal import Decimal

from app.purchase_calculations import calculate_feasibility


def run_once() -> float:
    started = time.perf_counter()
    result = calculate_feasibility(
        Decimal("750000"),
        Decimal("40000"),
        Decimal("20000"),
        Decimal("180000"),
        Decimal("0"),
        Decimal("650000"),
        Decimal("6.25"),
        30,
        Decimal("7000"),
        Decimal("80"),
        Decimal("1500"),
    )
    assert result.required_total == Decimal("810000.00")
    return (time.perf_counter() - started) * 1000


for _ in range(10):
    run_once()
durations = [run_once() for _ in range(100)]
p95 = statistics.quantiles(durations, n=100, method="inclusive")[94]
print(f"Runs: {len(durations)}")
print(f"p50: {statistics.median(durations):.2f} ms")
print(f"p95: {p95:.2f} ms")
print(f"maximum: {max(durations):.2f} ms")
print("Threshold: p95 < 50 ms")
print("Result: PASS" if p95 < 50 else "Result: FAIL")
