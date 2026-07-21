from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class TaxCalculationInput:
    """Jurisdiction-neutral values supplied to a tax engine."""

    gross_taxable_income: Decimal
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaxComponent:
    """One named contribution to a tax estimate; credits use negative amounts."""

    code: str
    display_name: str
    amount: Decimal


@dataclass(frozen=True)
class TaxEstimate:
    jurisdiction: str
    tax_year: str
    ruleset_version: str
    taxable_income: Decimal
    components: list[TaxComponent]
    total: Decimal
    net_income: Decimal
    warnings: list[str] = field(default_factory=list)


class TaxEngine(Protocol):
    jurisdiction: str
    tax_year: str
    ruleset_version: str

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]: ...

    def calculate(self, values: TaxCalculationInput) -> TaxEstimate: ...


class TaxProvider(Protocol):
    jurisdiction: str
    display_name: str
    supported_tax_years: tuple[str, ...]

    def tax_year_for_date(self, as_of: date) -> str: ...

    def get_engine(self, tax_year: str) -> TaxEngine: ...
