from app.retirement_providers.australia import provider as australia_provider
from app.retirement_providers.base import RetirementProvider

BUILTIN_PROVIDERS: tuple[RetirementProvider, ...] = (australia_provider,)
