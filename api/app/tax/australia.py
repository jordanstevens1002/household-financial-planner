from decimal import ROUND_HALF_UP, Decimal

from app.tax.base import TaxEstimate, TaxInput

CENT = Decimal("0.01")


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

    def calculate(self, values: TaxInput) -> TaxEstimate:
        gross = Decimal(str(values.gross_taxable_income))
        deductions = Decimal(str(values.deductions))
        reportable_super = Decimal(str(values.reportable_super_contributions))
        surcharge_rate = Decimal(str(values.medicare_levy_surcharge_rate))
        taxable = max(gross - deductions, Decimal("0"))
        raw_tax = _resident_income_tax(taxable) if values.resident else _foreign_income_tax(taxable)
        offset = min(raw_tax, _low_income_tax_offset(taxable)) if values.resident else Decimal("0")
        income_tax = raw_tax - offset
        medicare = (
            taxable * Decimal("0.02")
            if values.resident and values.include_medicare_levy
            else Decimal("0")
        )
        surcharge = taxable * surcharge_rate / Decimal("100") if values.resident else Decimal("0")
        repayment_income = taxable + reportable_super
        study = _study_loan_repayment(repayment_income) if values.has_study_loan else Decimal("0")
        total = income_tax + medicare + surcharge + study
        warnings = [
            "Estimate only; Medicare reductions, family thresholds and other offsets "
            "are not modelled."
        ]
        return TaxEstimate(
            jurisdiction=self.jurisdiction,
            tax_year=self.tax_year,
            taxable_income=_money(taxable),
            income_tax=_money(income_tax),
            offsets=_money(offset),
            medicare_levy=_money(medicare),
            medicare_levy_surcharge=_money(surcharge),
            study_loan_repayment=_money(study),
            total=_money(total),
            net_income=_money(gross - total),
            warnings=warnings,
        )


def get_australian_engine(tax_year: str) -> AustraliaTaxEngine2025_26:
    if tax_year != "2025-26":
        raise ValueError(f"Unsupported Australian tax year: {tax_year}")
    return AustraliaTaxEngine2025_26()
