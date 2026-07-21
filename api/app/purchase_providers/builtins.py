from app.purchase_providers.australia import provider as australia_provider
from app.purchase_providers.base import PurchaseProvider

BUILTIN_PROVIDERS: tuple[PurchaseProvider, ...] = (australia_provider,)
