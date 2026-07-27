"""Tax provider discovery and registry."""

from collections.abc import Iterable
from datetime import date
from functools import lru_cache
from importlib.metadata import entry_points

from app.income.tax.base import TaxEngine, TaxProvider
from app.income.tax.builtins import BUILTIN_PROVIDERS

ENTRY_POINT_GROUP = "household_financial_planner.tax_providers"


class TaxProviderError(ValueError):
    """Raised when a tax provider cannot be selected or loaded."""


class TaxProviderRegistry:
    def __init__(self, providers: Iterable[TaxProvider] = ()) -> None:
        self._providers: dict[str, TaxProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: TaxProvider) -> None:
        jurisdiction = provider.jurisdiction.strip().upper()
        if not jurisdiction:
            raise TaxProviderError("A tax provider must declare a jurisdiction")
        if jurisdiction in self._providers:
            raise TaxProviderError(f"Duplicate tax provider for jurisdiction: {jurisdiction}")
        self._providers[jurisdiction] = provider

    def get_provider(self, jurisdiction: str) -> TaxProvider:
        normalized = jurisdiction.strip().upper()
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise TaxProviderError(
                f"No tax provider is installed for jurisdiction: {normalized}"
            ) from exc

    def providers(self) -> tuple[TaxProvider, ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))


def _external_providers() -> list[TaxProvider]:
    providers: list[TaxProvider] = []
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        loaded = entry_point.load()
        provider = loaded() if isinstance(loaded, type) else loaded
        providers.append(provider)
    return providers


@lru_cache
def get_registry() -> TaxProviderRegistry:
    return TaxProviderRegistry([*BUILTIN_PROVIDERS, *_external_providers()])


def get_tax_engine(jurisdiction: str, tax_year: str) -> TaxEngine:
    try:
        return get_registry().get_provider(jurisdiction).get_engine(tax_year)
    except TaxProviderError:
        raise
    except ValueError as exc:
        raise TaxProviderError(str(exc)) from exc


def get_tax_engine_for_date(jurisdiction: str, as_of: date) -> tuple[TaxEngine, str, bool]:
    """Select the requested year's engine or the provider's newest available fallback."""
    provider = get_registry().get_provider(jurisdiction)
    expected_tax_year = provider.tax_year_for_date(as_of)
    supported = provider.supported_tax_years
    if not supported:
        raise TaxProviderError(
            f"Tax provider for {provider.jurisdiction} does not publish any tax years"
        )
    selected_tax_year = expected_tax_year if expected_tax_year in supported else supported[-1]
    try:
        engine = provider.get_engine(selected_tax_year)
    except ValueError as exc:
        raise TaxProviderError(str(exc)) from exc
    return engine, expected_tax_year, selected_tax_year != expected_tax_year


def tax_year_for_date(jurisdiction: str, as_of: date) -> str:
    return get_registry().get_provider(jurisdiction).tax_year_for_date(as_of)
