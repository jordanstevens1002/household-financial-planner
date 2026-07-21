from collections.abc import Iterable
from functools import lru_cache
from importlib.metadata import entry_points

from app.purchase_providers.base import PurchaseProvider
from app.purchase_providers.builtins import BUILTIN_PROVIDERS

ENTRY_POINT_GROUP = "household_financial_planner.purchase_providers"


class PurchaseProviderError(ValueError):
    pass


class PurchaseProviderRegistry:
    def __init__(self, providers: Iterable[PurchaseProvider] = ()) -> None:
        self._providers: dict[str, PurchaseProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: PurchaseProvider) -> None:
        code = provider.code.strip().upper()
        if not code or code in self._providers:
            raise PurchaseProviderError(f"Invalid or duplicate purchase provider code: {code}")
        self._providers[code] = provider

    def get_provider(self, code: str) -> PurchaseProvider:
        try:
            return self._providers[code.strip().upper()]
        except KeyError as exc:
            raise PurchaseProviderError(
                f"No purchase provider is installed for code: {code}"
            ) from exc


def _external_providers() -> list[PurchaseProvider]:
    result: list[PurchaseProvider] = []
    for item in entry_points(group=ENTRY_POINT_GROUP):
        loaded = item.load()
        result.append(loaded() if isinstance(loaded, type) else loaded)
    return result


@lru_cache
def get_registry() -> PurchaseProviderRegistry:
    return PurchaseProviderRegistry([*BUILTIN_PROVIDERS, *_external_providers()])


def get_purchase_provider(code: str) -> PurchaseProvider:
    return get_registry().get_provider(code)
