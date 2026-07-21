from app.tax.australia import provider as australia_provider
from app.tax.base import TaxProvider

BUILTIN_PROVIDERS: tuple[TaxProvider, ...] = (australia_provider,)
