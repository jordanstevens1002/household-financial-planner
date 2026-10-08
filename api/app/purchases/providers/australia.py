"""Bundled Australian purchase provider example."""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.purchases.providers.base import (
    ProviderCost,
    PurchaseContext,
    PurchaseProviderResult,
)


class AustralianPurchaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transfer_duty_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    buyer_surcharge_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    registration_fees: Decimal = Field(default=Decimal("0"), ge=0)


class AustralianPurchaseProvider:
    code = "AU_PURCHASE"
    display_name = "Australian purchase-cost example"

    def validate_settings(self, settings: dict[str, object]) -> dict[str, object]:
        return AustralianPurchaseSettings.model_validate(settings).model_dump(mode="json")

    def calculate(
        self, context: PurchaseContext, settings: dict[str, object]
    ) -> PurchaseProviderResult:
        values = AustralianPurchaseSettings.model_validate(settings)
        cent = Decimal("0.01")
        duty = (context.purchase_price * values.transfer_duty_rate / 100).quantize(
            cent, rounding=ROUND_HALF_UP
        )
        surcharge = (context.purchase_price * values.buyer_surcharge_rate / 100).quantize(
            cent, rounding=ROUND_HALF_UP
        )
        costs = [
            ProviderCost("transfer_duty", "Transfer duty estimate", duty),
            ProviderCost("buyer_surcharge", "Buyer surcharge estimate", surcharge),
            ProviderCost("registration", "Registration fees", values.registration_fees),
        ]
        warnings = ["Confirm duties and fees with the relevant authority before purchasing."]
        if all(item.amount == 0 for item in costs):
            warnings.append(
                "All Australian provider settings are zero; enter planning rates and fees "
                "before relying on its cost estimate."
            )
        if context.currency != "AUD":
            warnings.append(
                f"The Australian provider is calculating a {context.currency} plan; "
                "confirm the plan currency should not be AUD."
            )
        return PurchaseProviderResult(
            costs=costs,
            assumptions=[
                "Australian rates are user-entered planning inputs, not an official duty schedule."
            ],
            warnings=warnings,
        )


provider = AustralianPurchaseProvider()
