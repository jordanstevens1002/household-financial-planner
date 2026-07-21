from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.retirement_providers.base import RetirementProjectionRules


class AustralianSuperSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preservation_age: int = Field(default=60, ge=0, le=120)
    annual_pre_tax_cap: Decimal = Field(default=Decimal("30000"), ge=0)
    annual_post_tax_cap: Decimal = Field(default=Decimal("120000"), ge=0)


class AustralianSuperProvider:
    code = "AU_SUPER"
    display_name = "Australian superannuation"

    def validate_settings(self, settings: dict[str, object]) -> dict[str, object]:
        return AustralianSuperSettings.model_validate(settings).model_dump(mode="json")

    def validate_account_type(self, account_type_code: str) -> None:
        if account_type_code not in {"AUSTRALIAN_SUP", "SELF_MANAGED_SUP_FUND"}:
            raise ValueError(
                "AU_SUPER supports AUSTRALIAN_SUP and SELF_MANAGED_SUP_FUND account types"
            )

    def projection_rules(
        self, as_of: date, settings: dict[str, object]
    ) -> RetirementProjectionRules:
        values = AustralianSuperSettings.model_validate(settings)
        return RetirementProjectionRules(
            annual_pre_tax_cap=values.annual_pre_tax_cap,
            annual_post_tax_cap=values.annual_post_tax_cap,
            assumptions=[
                f"Australian super preservation age: {values.preservation_age}.",
                f"Australian provider settings evaluated at {as_of.isoformat()}.",
            ],
        )


provider = AustralianSuperProvider()
