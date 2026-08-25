import io
import zipfile
from copy import copy
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from app.investments.capital_gains import calculate_fifo
from scripts.stake_cgt import read_stake_workbook, render_markdown


def capitalise_excel_alignment(path: Path) -> None:
    source_bytes = path.read_bytes()
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(source_bytes)) as source,
        zipfile.ZipFile(output, "w") as target,
    ):
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/styles.xml":
                content = content.replace(b'horizontal="center"', b'horizontal="Center"')
            target.writestr(item, content)
    path.write_bytes(output.getvalue())


def test_reads_sectioned_stake_workbook_and_renders_report(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Investment Activity"
    sheet.append(["Aus Equities"])
    sheet.append(
        [
            "Date",
            "Settlement",
            "Side",
            "Identifier",
            "Units",
            "Avg. Price",
            "Value",
            "Trade Fees",
            "GST",
            "Total Value",
        ]
    )
    sheet.append(["ABC - Example Limited"])
    sheet.append([date(2024, 1, 1), None, "Buy", "buy-1", 10, 10, 100, 2.73, 0.27, 103])
    sheet.append([date(2026, 1, 2), None, "Sell", "sell-1", -10, 20, -200, 2.73, 0.27, -197])
    path = tmp_path / "activity.xlsx"
    workbook.save(path)

    trades = read_stake_workbook(path)
    report = render_markdown(calculate_fifo(trades), "2025-26")

    assert len(trades) == 2
    assert trades[0].total_aud == Decimal("103")
    assert "| $94.00 | $0.00 | $94.00 |" in report
    assert "| 2026-01-02 | Stake AUS | ABC | 10 | $197.00 | $103.00 | $94.00" in report


def test_tolerates_stake_nonstandard_alignment_capitalisation(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Side", "Identifier", "Units", "Total Value", "Aus Equities"])
    sheet.append(["ABC - Example Limited"])
    sheet.append([date(2024, 1, 1), "Buy", "buy-1", 10, 103])
    alignment = copy(sheet["A1"].alignment)
    alignment.horizontal = "center"
    sheet["A1"].alignment = alignment
    path = tmp_path / "stake-invalid-style.xlsx"
    workbook.save(path)
    capitalise_excel_alignment(path)

    trades = read_stake_workbook(path)

    assert len(trades) == 1
    assert trades[0].identifier == "buy-1"
