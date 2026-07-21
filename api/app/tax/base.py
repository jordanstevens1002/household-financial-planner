from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class TaxInput:
    gross_taxable_income: Decimal
    deductions: Decimal = Decimal("0")
    reportable_super_contributions: Decimal = Decimal("0")
    resident: bool = True
    include_medicare_levy: bool = True
    medicare_levy_surcharge_rate: Decimal = Decimal("0")
    has_study_loan: bool = False


@dataclass(frozen=True)
class TaxEstimate:
    jurisdiction: str
    tax_year: str
    taxable_income: Decimal
    income_tax: Decimal
    offsets: Decimal
    medicare_levy: Decimal
    medicare_levy_surcharge: Decimal
    study_loan_repayment: Decimal
    total: Decimal
    net_income: Decimal
    warnings: list[str] = field(default_factory=list)


class TaxEngine(Protocol):
    jurisdiction: str
    tax_year: str

    def calculate(self, values: TaxInput) -> TaxEstimate: ...
