from datetime import date
from decimal import Decimal

import pytest

from app.retirement_providers.base import RetirementProjectionRules
from app.retirement_providers.registry import (
    RetirementProviderError,
    RetirementProviderRegistry,
)


class ExampleProvider:
    code = "EX_PLAN"
    display_name = "Example retirement plan"

    def validate_settings(self, settings: dict[str, object]) -> dict[str, object]:
        return {"limit": str(settings.get("limit", "50000"))}

    def validate_account_type(self, account_type_code: str) -> None:
        if account_type_code != "EMPLOYER_PLAN":
            raise ValueError("Unsupported account type")

    def projection_rules(
        self, as_of: date, settings: dict[str, object]
    ) -> RetirementProjectionRules:
        return RetirementProjectionRules(
            annual_pre_tax_cap=Decimal(str(settings["limit"])),
            assumptions=[f"Example rules for {as_of.year}."],
        )


def test_non_australian_provider_uses_generic_contract() -> None:
    registry = RetirementProviderRegistry([ExampleProvider()])
    provider = registry.get_provider("ex_plan")
    settings = provider.validate_settings({"limit": 45000})
    provider.validate_account_type("EMPLOYER_PLAN")
    rules = provider.projection_rules(date(2027, 1, 1), settings)

    assert rules.annual_pre_tax_cap == Decimal("45000")
    assert rules.assumptions == ["Example rules for 2027."]


def test_retirement_provider_registry_rejects_missing_and_duplicate_codes() -> None:
    registry = RetirementProviderRegistry([ExampleProvider()])
    with pytest.raises(RetirementProviderError, match="No retirement provider"):
        registry.get_provider("missing")
    with pytest.raises(RetirementProviderError, match="Duplicate retirement provider"):
        registry.register(ExampleProvider())
