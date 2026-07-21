from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.tax.base import TaxCalculationInput, TaxComponent, TaxEngine, TaxEstimate

CENT = Decimal("0.01")


class AustraliaTaxParameters(BaseModel):
    """Inputs understood by the bundled Australian tax provider."""

    model_config = ConfigDict(extra="forbid")

    resident: bool = True
    deductions: Decimal = Field(default=Decimal("0"), ge=0)
    reportable_super_contributions: Decimal = Field(default=Decimal("0"), ge=0)
    include_medicare_levy: bool = True
    medicare_levy_surcharge_rate: Decimal = Field(default=Decimal("0"), ge=0, le=2)
    has_study_loan: bool = False


def _money(value: Decimal) -> Decimal:
    return max(value, Decimal("0")).quantize(CENT, rounding=ROUND_HALF_UP)


def _resident_income_tax(income: Decimal) -> Decimal:
    if income <= Decimal("18200"):
        return Decimal("0")
    if income <= Decimal("45000"):
        return (income - Decimal("18200")) * Decimal("0.16")
    if income <= Decimal("135000"):
        return Decimal("4288") + (income - Decimal("45000")) * Decimal("0.30")
    if income <= Decimal("190000"):
        return Decimal("31288") + (income - Decimal("135000")) * Decimal("0.37")
    return Decimal("51638") + (income - Decimal("190000")) * Decimal("0.45")


def _foreign_income_tax(income: Decimal) -> Decimal:
    if income <= Decimal("135000"):
        return income * Decimal("0.30")
    if income <= Decimal("190000"):
        return Decimal("40500") + (income - Decimal("135000")) * Decimal("0.37")
    return Decimal("60850") + (income - Decimal("190000")) * Decimal("0.45")


def _low_income_tax_offset(income: Decimal) -> Decimal:
    if income <= Decimal("37500"):
        return Decimal("700")
    if income <= Decimal("45000"):
        return Decimal("700") - (income - Decimal("37500")) * Decimal("0.05")
    if income <= Decimal("66667"):
        return Decimal("325") - (income - Decimal("45000")) * Decimal("0.015")
    return Decimal("0")


def _study_loan_repayment(repayment_income: Decimal) -> Decimal:
    if repayment_income <= Decimal("67000"):
        return Decimal("0")
    if repayment_income <= Decimal("125000"):
        return (repayment_income - Decimal("67000")) * Decimal("0.15")
    if repayment_income <= Decimal("179285"):
        return Decimal("8700") + (repayment_income - Decimal("125000")) * Decimal("0.17")
    return repayment_income * Decimal("0.10")


class AustraliaTaxEngine2025_26:
    jurisdiction = "AU"
    tax_year = "2025-26"
    ruleset_version = "AU-2025-26-v1"

    def validate_parameters(self, parameters: dict[str, object]) -> dict[str, object]:
        return AustraliaTaxParameters.model_validate(parameters).model_dump(mode="json")

    def calculate(self, values: TaxCalculationInput) -> TaxEstimate:
        parameters = AustraliaTaxParameters.model_validate(
            self.validate_parameters(values.parameters)
        )
        gross = Decimal(str(values.gross_taxable_income))
        taxable = max(gross - parameters.deductions, Decimal("0"))
        raw_tax = (
            _resident_income_tax(taxable) if parameters.resident else _foreign_income_tax(taxable)
        )
        offset = (
            min(raw_tax, _low_income_tax_offset(taxable)) if parameters.resident else Decimal("0")
        )
        medicare = (
            taxable * Decimal("0.02")
            if parameters.resident and parameters.include_medicare_levy
            else Decimal("0")
        )
        surcharge = (
            taxable * parameters.medicare_levy_surcharge_rate / Decimal("100")
            if parameters.resident
            else Decimal("0")
        )
        repayment_income = taxable + parameters.reportable_super_contributions
        study = (
            _study_loan_repayment(repayment_income) if parameters.has_study_loan else Decimal("0")
        )
        components = [
            TaxComponent("income_tax", "Income tax", _money(raw_tax)),
            TaxComponent("low_income_tax_offset", "Low income tax offset", -_money(offset)),
            TaxComponent("medicare_levy", "Medicare levy", _money(medicare)),
            TaxComponent("medicare_levy_surcharge", "Medicare levy surcharge", _money(surcharge)),
            TaxComponent("study_loan_repayment", "Study loan repayment", _money(study)),
        ]
        total = sum((component.amount for component in components), Decimal("0"))
        return TaxEstimate(
            jurisdiction=self.jurisdiction,
            tax_year=self.tax_year,
            ruleset_version=self.ruleset_version,
            taxable_income=_money(taxable),
            components=components,
            total=_money(total),
            net_income=_money(gross - total),
            warnings=[
                "Estimate only; Medicare reductions, family thresholds and other offsets "
                "are not modelled."
            ],
        )


class AustraliaTaxProvider:
    jurisdiction = "AU"
    display_name = "Australia"
    supported_tax_years: tuple[str, ...] = ("2025-26",)

    def tax_year_for_date(self, as_of: date) -> str:
        start_year = as_of.year if as_of.month >= 7 else as_of.year - 1
        return f"{start_year}-{(start_year + 1) % 100:02d}"

    def get_engine(self, tax_year: str) -> TaxEngine:
        if tax_year != "2025-26":
            raise ValueError(f"Unsupported Australian tax year: {tax_year}")
        return AustraliaTaxEngine2025_26()


provider = AustraliaTaxProvider()
