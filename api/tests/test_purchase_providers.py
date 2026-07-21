from datetime import date
from decimal import Decimal

import pytest

from app.purchase_providers.base import PurchaseContext, PurchaseProviderResult
from app.purchase_providers.registry import PurchaseProviderError, PurchaseProviderRegistry


class ExampleProvider:
    code = "EX_PURCHASE"
    display_name = "Example"

    def validate_settings(self, settings: dict[str, object]) -> dict[str, object]:
        return settings

    def calculate(
        self, context: PurchaseContext, settings: dict[str, object]
    ) -> PurchaseProviderResult:
        return PurchaseProviderResult(assumptions=[f"Example {context.currency}"])


def test_non_australian_purchase_provider_uses_generic_contract() -> None:
    registry = PurchaseProviderRegistry([ExampleProvider()])
    provider = registry.get_provider("ex_purchase")
    assert provider.validate_settings({"option": True}) == {"option": True}
    result = provider.calculate(
        PurchaseContext(
            Decimal("100000"),
            "BUSINESS",
            {"region": "Example"},
            "OPERATE",
            date(2027, 1, 1),
            "XYZ",
        ),
        {},
    )
    assert result.assumptions == ["Example XYZ"]


def test_purchase_provider_registry_rejects_missing_and_duplicates() -> None:
    registry = PurchaseProviderRegistry([ExampleProvider()])
    with pytest.raises(PurchaseProviderError, match="No purchase provider"):
        registry.get_provider("missing")
    with pytest.raises(PurchaseProviderError, match="duplicate"):
        registry.register(ExampleProvider())
