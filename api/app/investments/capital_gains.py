"""Parcel-level capital gain calculations for imported investment activity."""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Trade:
    account: str
    security: str
    traded_on: date
    side: str
    units: Decimal
    total_aud: Decimal
    identifier: str
    source: str


@dataclass(frozen=True)
class ParcelMatch:
    acquired_on: date
    units: Decimal
    cost_base_aud: Decimal
    discount_eligible: bool
    acquisition_identifier: str


@dataclass(frozen=True)
class Disposal:
    account: str
    security: str
    disposed_on: date
    units: Decimal
    proceeds_aud: Decimal
    matched_cost_base_aud: Decimal
    unmatched_units: Decimal
    gain_or_loss_aud: Decimal | None
    discount_eligible_gain_aud: Decimal
    identifier: str
    source: str
    matches: tuple[ParcelMatch, ...]


@dataclass(frozen=True)
class Calculation:
    disposals: tuple[Disposal, ...]
    warnings: tuple[str, ...]


@dataclass
class _Lot:
    acquired_on: date
    units: Decimal
    cost_base_aud: Decimal
    identifier: str


def _discount_eligible(acquired_on: date, disposed_on: date) -> bool:
    """Use the conservative ATO test: disposal must be after the first anniversary."""
    try:
        anniversary = acquired_on.replace(year=acquired_on.year + 1)
    except ValueError:  # 29 February
        anniversary = acquired_on.replace(year=acquired_on.year + 1, day=28)
    return disposed_on > anniversary


def calculate_fifo(trades: list[Trade]) -> Calculation:
    """Match disposals to earlier acquisitions using an explicit FIFO assumption.

    ``total_aud`` is the cash total: positive inclusive cost for buys and net proceeds
    for sells (which can be negative when fees exceed gross proceeds). A result is
    deliberately withheld when any sold units have no imported cost-base parcel.
    """
    lots: dict[tuple[str, str], deque[_Lot]] = defaultdict(deque)
    disposals: list[Disposal] = []
    warnings: list[str] = []
    ordered = sorted(enumerate(trades), key=lambda item: (item[1].traded_on, item[0]))

    for _, trade in ordered:
        if trade.units <= 0 or (trade.side == "BUY" and trade.total_aud < 0):
            raise ValueError(f"Invalid units/value in {trade.source}: {trade.identifier}")
        key = (trade.account, trade.security)
        if trade.side == "BUY":
            lots[key].append(_Lot(trade.traded_on, trade.units, trade.total_aud, trade.identifier))
            continue
        if trade.side != "SELL":
            raise ValueError(f"Unsupported side {trade.side!r} in {trade.source}")

        remaining = trade.units
        matched_cost = Decimal("0")
        matches: list[ParcelMatch] = []
        while remaining > 0 and lots[key]:
            lot = lots[key][0]
            matched_units = min(remaining, lot.units)
            matched_cost_for_units = lot.cost_base_aud * matched_units / lot.units
            eligible = _discount_eligible(lot.acquired_on, trade.traded_on)
            matches.append(
                ParcelMatch(
                    acquired_on=lot.acquired_on,
                    units=matched_units,
                    cost_base_aud=matched_cost_for_units,
                    discount_eligible=eligible,
                    acquisition_identifier=lot.identifier,
                )
            )
            matched_cost += matched_cost_for_units
            lot.units -= matched_units
            lot.cost_base_aud -= matched_cost_for_units
            remaining -= matched_units
            if lot.units == 0:
                lots[key].popleft()

        result = trade.total_aud - matched_cost if remaining == 0 else None
        eligible_gain = Decimal("0")
        if result is not None and result > 0:
            proceeds_per_unit = trade.total_aud / trade.units
            for match in matches:
                parcel_gain = proceeds_per_unit * match.units - match.cost_base_aud
                if match.discount_eligible and parcel_gain > 0:
                    eligible_gain += parcel_gain
        if remaining:
            warnings.append(
                f"{trade.security} sale {trade.identifier} has {remaining} unmatched units; "
                "import earlier activity and any corporate actions."
            )
        disposals.append(
            Disposal(
                account=trade.account,
                security=trade.security,
                disposed_on=trade.traded_on,
                units=trade.units,
                proceeds_aud=trade.total_aud,
                matched_cost_base_aud=matched_cost,
                unmatched_units=remaining,
                gain_or_loss_aud=result,
                discount_eligible_gain_aud=eligible_gain,
                identifier=trade.identifier,
                source=trade.source,
                matches=tuple(matches),
            )
        )
    return Calculation(tuple(disposals), tuple(warnings))
