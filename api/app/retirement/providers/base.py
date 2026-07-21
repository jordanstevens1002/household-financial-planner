"""Country-neutral retirement provider contracts."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class RetirementProjectionRules:
    annual_pre_tax_cap: Decimal | None = None
    annual_post_tax_cap: Decimal | None = None
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RetirementProvider(Protocol):
    code: str
    display_name: str

    def validate_settings(self, settings: dict[str, object]) -> dict[str, object]: ...

    def validate_account_type(self, account_type_code: str) -> None: ...

    def projection_rules(
        self, as_of: date, settings: dict[str, object]
    ) -> RetirementProjectionRules: ...
