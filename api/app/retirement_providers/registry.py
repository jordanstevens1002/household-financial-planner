from collections.abc import Iterable
from functools import lru_cache
from importlib.metadata import entry_points

from app.retirement_providers.base import RetirementProvider
from app.retirement_providers.builtins import BUILTIN_PROVIDERS

ENTRY_POINT_GROUP = "household_financial_planner.retirement_providers"


class RetirementProviderError(ValueError):
    pass


class RetirementProviderRegistry:
    def __init__(self, providers: Iterable[RetirementProvider] = ()) -> None:
        self._providers: dict[str, RetirementProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: RetirementProvider) -> None:
        code = provider.code.strip().upper()
        if not code:
            raise RetirementProviderError("A retirement provider must declare a code")
        if code in self._providers:
            raise RetirementProviderError(f"Duplicate retirement provider code: {code}")
        self._providers[code] = provider

    def get_provider(self, code: str) -> RetirementProvider:
        normalized = code.strip().upper()
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise RetirementProviderError(
                f"No retirement provider is installed for code: {normalized}"
            ) from exc


def _external_providers() -> list[RetirementProvider]:
    providers: list[RetirementProvider] = []
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        loaded = entry_point.load()
        providers.append(loaded() if isinstance(loaded, type) else loaded)
    return providers


@lru_cache
def get_registry() -> RetirementProviderRegistry:
    return RetirementProviderRegistry([*BUILTIN_PROVIDERS, *_external_providers()])


def get_retirement_provider(code: str) -> RetirementProvider:
    return get_registry().get_provider(code)
