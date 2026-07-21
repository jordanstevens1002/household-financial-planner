from datetime import date
from decimal import Decimal

import pytest

from app.tax.base import TaxCalculationInput, TaxComponent, TaxEstimate
from app.tax.registry import TaxProviderError, TaxProviderRegistry


class ExampleEngine:
    jurisdiction = "EX"
    tax_year = "2026"
    ruleset_version = "EX-2026-v1"

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]:
        return parameters

    def calculate(self, values: TaxCalculationInput) -> TaxEstimate:
        rate = Decimal(str(values.parameters.get("rate", "0.10")))
        total = values.gross_taxable_income * rate
        return TaxEstimate(
            jurisdiction=self.jurisdiction,
            tax_year=self.tax_year,
            ruleset_version=self.ruleset_version,
            taxable_income=values.gross_taxable_income,
            components=[TaxComponent("income_tax", "Income tax", total)],
            total=total,
            net_income=values.gross_taxable_income - total,
        )


class ExampleProvider:
    jurisdiction = "EX"
    display_name = "Example jurisdiction"
    supported_tax_years = ("2026",)

    def tax_year_for_date(self, as_of: date) -> str:
        return str(as_of.year)

    def get_engine(self, tax_year: str) -> ExampleEngine:
        if tax_year not in self.supported_tax_years:
            raise ValueError(f"Unsupported example tax year: {tax_year}")
        return ExampleEngine()


def test_custom_provider_uses_generic_contract_without_core_income_changes() -> None:
    registry = TaxProviderRegistry([ExampleProvider()])
    provider = registry.get_provider("ex")
    result = provider.get_engine("2026").calculate(
        TaxCalculationInput(Decimal("100000"), {"rate": "0.15"})
    )

    assert provider.tax_year_for_date(date(2026, 7, 1)) == "2026"
    assert result.ruleset_version == "EX-2026-v1"
    assert result.total == Decimal("15000.00")
    assert result.net_income == Decimal("85000.00")


def test_registry_rejects_missing_and_duplicate_providers() -> None:
    registry = TaxProviderRegistry([ExampleProvider()])
    with pytest.raises(TaxProviderError, match="No tax provider"):
        registry.get_provider("missing")
    with pytest.raises(TaxProviderError, match="Duplicate tax provider"):
        registry.register(ExampleProvider())
