from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class PurchaseContext:
    purchase_price: Decimal
    purchase_type_code: str
    target_location: dict[str, object]
    intended_use: str
    target_date: date
    currency: str


@dataclass(frozen=True)
class ProviderCost:
    code: str
    display_name: str
    amount: Decimal


@dataclass(frozen=True)
class PurchaseProviderResult:
    costs: list[ProviderCost] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PurchaseProvider(Protocol):
    code: str
    display_name: str

    def validate_settings(self, settings: dict[str, object]) -> dict[str, object]: ...

    def calculate(
        self, context: PurchaseContext, settings: dict[str, object]
    ) -> PurchaseProviderResult: ...
