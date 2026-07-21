"""Cross-cutting architecture tests."""

from pathlib import Path

from app.income.tax.builtins import BUILTIN_PROVIDERS
from app.income.tax.registry import TaxProviderRegistry
from app.models import OwnerType


def test_shared_owner_types_use_retirement_neutral_language() -> None:
    values = {item.value for item in OwnerType}
    assert "RETIREMENT_FUND" in values
    assert "SUPER_FUND" not in values


def test_bundled_tax_examples_use_the_neutral_registry_contract() -> None:
    registry = TaxProviderRegistry(BUILTIN_PROVIDERS)
    for provider in BUILTIN_PROVIDERS:
        assert registry.get_provider(provider.jurisdiction) is provider


def test_application_and_tests_share_domain_oriented_packages() -> None:
    root = Path(__file__).parents[2]
    app_root = root / "app"
    tests_root = root / "tests"
    domains = {
        "core",
        "events",
        "households",
        "income",
        "loans",
        "properties",
        "purchases",
        "rental",
        "retirement",
        "scenarios",
    }
    assert {item.name for item in app_root.iterdir() if item.is_file()} <= {
        "__init__.py",
        "main.py",
        "models.py",
    }
    assert domains <= {item.name for item in app_root.iterdir() if item.is_dir()}
    assert domains <= {item.name for item in tests_root.iterdir() if item.is_dir()}
