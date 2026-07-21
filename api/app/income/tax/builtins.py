"""Bundled tax provider registration."""

from app.income.tax.australia import provider as australia_provider
from app.income.tax.base import TaxProvider

BUILTIN_PROVIDERS: tuple[TaxProvider, ...] = (australia_provider,)
