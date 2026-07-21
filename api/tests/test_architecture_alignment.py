from app.models import OwnerType
from app.tax.builtins import BUILTIN_PROVIDERS
from app.tax.registry import TaxProviderRegistry


def test_shared_owner_types_use_retirement_neutral_language() -> None:
    values = {item.value for item in OwnerType}
    assert "RETIREMENT_FUND" in values
    assert "SUPER_FUND" not in values


def test_bundled_tax_examples_use_the_neutral_registry_contract() -> None:
    registry = TaxProviderRegistry(BUILTIN_PROVIDERS)
    for provider in BUILTIN_PROVIDERS:
        assert registry.get_provider(provider.jurisdiction) is provider
