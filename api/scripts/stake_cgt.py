#!/usr/bin/env python3
"""Create an experimental CGT working paper from Stake activity XLSX files."""

import argparse
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.investments.capital_gains import Calculation, Trade, calculate_fifo

HEADERS = {"date", "side", "identifier", "units", "total value"}
SECURITY = re.compile(r"^\s*([A-Z0-9.:-]+)\s+-\s+(.+?)\s*$")
FY = re.compile(r"^(\d{4})-(\d{2}|\d{4})$")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    cleaned = re.sub(r"[^0-9.()-]", "", str(value))
    if not cleaned:
        return None
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value:
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(value).strip(), pattern).date()
            except ValueError:
                pass
    return None


def _is_aud(cell: Any) -> bool:
    rendered = _text(cell.value).upper()
    number_format = _text(cell.number_format).upper()
    return "AUD" in rendered or "AUD" in number_format or "A$" in rendered


def read_stake_workbook(path: Path) -> list[Trade]:
    """Read Stake's sectioned Investment Activity workbook.

    Stake Wall St trades can contain a USD display row followed by an AUD display row.
    Only the AUD row is retained. Australian rows without an explicit currency marker are
    treated as AUD. Header aliases are intentionally strict so format changes fail visibly.
    """
    workbook = load_workbook(path, read_only=True, data_only=True)
    trades: list[Trade] = []
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows())
        header_at: int | None = None
        columns: dict[str, int] = {}
        for index, row in enumerate(rows):
            values = [_text(cell.value).lower() for cell in row]
            if HEADERS.issubset(set(values)):
                header_at = index
                columns = {value: position for position, value in enumerate(values) if value}
                break
        if header_at is None:
            continue

        account = sheet.title
        introductory_text = " ".join(
            _text(cell.value) for row in rows[: header_at + 1] for cell in row
        )
        if "Wall St Equities" in introductory_text:
            account = "Stake Wall St"
        elif "Aus Equities" in introductory_text:
            account = "Stake AUS"
        security = ""
        pending: dict[str, Any] | None = None
        for row_number, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
            values = [_text(cell.value) for cell in row]
            joined = " ".join(value for value in values if value)
            if "Wall St Equities" in joined:
                account = "Stake Wall St"
            elif "Aus Equities" in joined:
                account = "Stake AUS"
            security_match = next(
                (SECURITY.match(value) for value in values if SECURITY.match(value)), None
            )
            if security_match and not any(value.upper() in {"BUY", "SELL"} for value in values):
                security = security_match.group(1)
                continue

            side = values[columns["side"]].upper() if columns["side"] < len(values) else ""
            traded_on = _date(row[columns["date"]].value) if columns["date"] < len(row) else None
            if side in {"BUY", "SELL"} and traded_on:
                pending = {
                    "account": account,
                    "security": security,
                    "traded_on": traded_on,
                    "side": side,
                    "units": abs(_decimal(row[columns["units"]].value) or Decimal("0")),
                    "identifier": values[columns["identifier"]],
                    "row": row_number,
                    "currency_rows": 0,
                }
            if pending is None:
                continue

            total_cell = row[columns["total value"]]
            total = _decimal(total_cell.value)
            is_wall_st = pending["account"] == "Stake Wall St"
            if total is None:
                continue
            pending["currency_rows"] += 1
            if is_wall_st and not _is_aud(total_cell) and pending["currency_rows"] < 2:
                continue
            if not pending["security"]:
                raise ValueError(f"No security heading before row {row_number} in {path}")
            trades.append(
                Trade(
                    account=pending["account"],
                    security=pending["security"],
                    traded_on=pending["traded_on"],
                    side=pending["side"],
                    units=pending["units"],
                    total_aud=abs(total),
                    identifier=pending["identifier"],
                    source=f"{path.name}:{pending['row']}",
                )
            )
            pending = None
    if not trades:
        raise ValueError(f"No Stake investment activity rows found in {path}")
    return trades


def _fy_bounds(value: str) -> tuple[date, date]:
    match = FY.match(value)
    if not match:
        raise argparse.ArgumentTypeError("financial year must look like 2025-26")
    start_year = int(match.group(1))
    end_text = match.group(2)
    end_year = int(end_text) if len(end_text) == 4 else (start_year // 100) * 100 + int(end_text)
    if end_year != start_year + 1:
        raise argparse.ArgumentTypeError("financial year must span consecutive years")
    return date(start_year, 7, 1), date(end_year, 6, 30)


def render_markdown(calculation: Calculation, financial_year: str | None) -> str:
    disposals = calculation.disposals
    if financial_year:
        start, end = _fy_bounds(financial_year)
        disposals = tuple(item for item in disposals if start <= item.disposed_on <= end)
    complete = [item for item in disposals if item.gain_or_loss_aud is not None]
    gains = sum(
        (item.gain_or_loss_aud for item in complete if item.gain_or_loss_aud > 0), Decimal()
    )
    losses = -sum(
        (item.gain_or_loss_aud for item in complete if item.gain_or_loss_aud < 0), Decimal()
    )
    discount_gains = sum((item.discount_eligible_gain_aud for item in complete), Decimal())
    title = (
        f"Stake CGT working paper — {financial_year}"
        if financial_year
        else "Stake CGT working paper — all disposals"
    )
    lines = [
        f"# {title}",
        "",
        "> Experimental working paper only. It uses FIFO parcel matching and is not tax advice.",
        "> Incomplete disposals are excluded from totals. Verify against contract notes, issuer",
        "> tax statements and corporate-action records before reporting to the ATO.",
        "",
        "## Summary",
        "",
        "| Complete gross gains | Complete capital losses | Discount-eligible gross gains |",
        "| ---: | ---: | ---: |",
        f"| ${gains:.2f} | ${losses:.2f} | ${discount_gains:.2f} |",
        "",
        "The discount-eligible amount is shown before applying current-year or "
        "carried-forward losses.",
        "It is not the net capital gain for the tax return.",
        "",
        "## Disposals",
        "",
        "| Date | Account | Security | Units | Net proceeds (AUD) | Cost base (AUD) | "
        "Gain/(loss) | Discount-eligible gain | Status | Trade ID | Source |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in disposals:
        result = "incomplete" if item.gain_or_loss_aud is None else f"${item.gain_or_loss_aud:.2f}"
        status = (
            f"missing cost base for {item.unmatched_units} units"
            if item.unmatched_units
            else "complete"
        )
        lines.append(
            f"| {item.disposed_on} | {item.account} | {item.security} | {item.units} | "
            f"${item.proceeds_aud:.2f} | ${item.matched_cost_base_aud:.2f} | {result} | "
            f"${item.discount_eligible_gain_aud:.2f} | {status} | {item.identifier} | "
            f"{item.source} |"
        )
    if not disposals:
        lines.append("| — | — | — | — | — | — | — | — | No disposals found | — | — |")
    lines.extend(["", "## Parcel matching", ""])
    for item in disposals:
        lines.append(f"### {item.security} — sale {item.identifier}")
        lines.append("")
        lines.append(
            "| Acquisition date | Units | Allocated cost base (AUD) | Discount eligible | Buy ID |"
        )
        lines.append("| --- | ---: | ---: | --- | --- |")
        for match in item.matches:
            eligible = "yes" if match.discount_eligible else "no"
            lines.append(
                f"| {match.acquired_on} | {match.units} | ${match.cost_base_aud:.2f} | "
                f"{eligible} | {match.acquisition_identifier} |"
            )
        if not item.matches:
            lines.append("| — | — | — | — | No imported acquisition matched |")
        lines.append("")
    if calculation.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in calculation.warnings)
        lines.append("")
    lines.extend(
        [
            "## Method and assumptions",
            "",
            "- Trade date determines the income year.",
            "- Stake's AUD total is used: inclusive cost for buys and net proceeds for sells.",
            "- Parcels are matched FIFO within each Stake account and security.",
            "- Discount eligibility is flagged only when disposal is after the first "
            "acquisition anniversary.",
            "- Corporate actions, transfers, AMIT cost-base adjustments and non-market "
            "acquisitions are not inferred.",
            "- Values are calculated at full precision and displayed to the nearest cent.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("--output", type=Path, default=Path("stake-cgt-working-paper.md"))
    parser.add_argument("--financial-year", help="Australian financial year, for example 2025-26")
    args = parser.parse_args()
    files = sorted(args.input_directory.glob("*.xlsx"))
    if not files:
        parser.error(f"no .xlsx files found in {args.input_directory}")
    try:
        trades = [trade for path in files for trade in read_stake_workbook(path)]
        report = render_markdown(calculate_fifo(trades), args.financial_year)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output} from {len(files)} workbook(s) and {len(trades)} trades.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
