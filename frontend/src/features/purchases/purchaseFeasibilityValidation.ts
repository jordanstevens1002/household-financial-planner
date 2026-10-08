export interface FeasibilityDraft {
  annualInterestRate: string;
  currentMonthlySurplus: string;
  desiredBuffer: string;
  loanTermYears: string;
  maximumAdditionalBorrowing: string;
  purchasePrice: string;
}

const unsignedMoney = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const signedMoney = /^-?(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const ratePattern = /^(?:100(?:\.0{1,4})?|\d{1,2}(?:\.\d{1,4})?)$/;

export function validateFeasibilityDraft(
  draft: FeasibilityDraft,
): string | null {
  if (!unsignedMoney.test(draft.purchasePrice) || draft.purchasePrice === '0')
    return 'Purchase price must be greater than zero with no more than two decimal places.';
  if (!unsignedMoney.test(draft.maximumAdditionalBorrowing))
    return 'Maximum additional borrowing must be a non-negative amount with no more than two decimal places.';
  if (draft.desiredBuffer && !unsignedMoney.test(draft.desiredBuffer))
    return 'Desired buffer must be a non-negative amount with no more than two decimal places.';
  if (!signedMoney.test(draft.currentMonthlySurplus))
    return 'Current monthly surplus must be an amount with no more than two decimal places.';
  if (!ratePattern.test(draft.annualInterestRate))
    return 'Annual interest rate must be between 0 and 100 with no more than four decimal places.';
  const term = Number(draft.loanTermYears);
  if (!/^\d+$/.test(draft.loanTermYears) || term < 1 || term > 100)
    return 'Loan term must be a whole number from 1 to 100 years.';
  return null;
}
