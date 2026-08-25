from datetime import date
from decimal import Decimal

from app.investments.capital_gains import Trade, calculate_fifo


def trade(day: str, side: str, units: str, total: str, identifier: str = "trade") -> Trade:
    return Trade(
        account="Stake Wall St",
        security="XYZ",
        traded_on=date.fromisoformat(day),
        side=side,
        units=Decimal(units),
        total_aud=Decimal(total),
        identifier=identifier,
        source="test.xlsx:1",
    )


def test_fifo_matches_parcels_and_allocates_partial_cost_base() -> None:
    result = calculate_fifo(
        [
            trade("2023-01-01", "BUY", "10", "100", "buy-1"),
            trade("2025-01-04", "BUY", "10", "200", "buy-2"),
            trade("2026-01-04", "SELL", "15", "450", "sell"),
        ]
    )

    disposal = result.disposals[0]
    assert disposal.matched_cost_base_aud == Decimal("200")
    assert disposal.gain_or_loss_aud == Decimal("250")
    assert disposal.discount_eligible_gain_aud == Decimal("200")
    assert [match.units for match in disposal.matches] == [Decimal("10"), Decimal("5")]


def test_missing_history_does_not_report_a_false_gain() -> None:
    result = calculate_fifo([trade("2026-01-04", "SELL", "3", "90", "sell")])

    assert result.disposals[0].gain_or_loss_aud is None
    assert result.disposals[0].unmatched_units == Decimal("3")
    assert "unmatched units" in result.warnings[0]
