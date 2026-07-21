"""Bundled purchase provider registration."""

from app.purchases.providers.australia import provider as australia_provider
from app.purchases.providers.base import PurchaseProvider

BUILTIN_PROVIDERS: tuple[PurchaseProvider, ...] = (australia_provider,)
