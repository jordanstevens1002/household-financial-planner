"""Bundled retirement provider registration."""

from app.retirement.providers.australia import provider as australia_provider
from app.retirement.providers.base import RetirementProvider

BUILTIN_PROVIDERS: tuple[RetirementProvider, ...] = (australia_provider,)
