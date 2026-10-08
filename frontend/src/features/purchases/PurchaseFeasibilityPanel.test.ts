import {
  type FeasibilityDraft,
  validateFeasibilityDraft,
} from './purchaseFeasibilityValidation';

const valid: FeasibilityDraft = {
  annualInterestRate: '6.1234',
  currentMonthlySurplus: '-100.00',
  desiredBuffer: '',
  loanTermYears: '30',
  maximumAdditionalBorrowing: '500000.00',
  purchasePrice: '750000.00',
};

describe('purchase feasibility validation', () => {
  it.each([
    ['purchasePrice', '0', 'Purchase price'],
    ['maximumAdditionalBorrowing', '-1', 'Maximum additional borrowing'],
    ['desiredBuffer', '1e5', 'Desired buffer'],
    ['currentMonthlySurplus', '10.001', 'Current monthly surplus'],
    ['annualInterestRate', '100.01', 'Annual interest rate'],
    ['loanTermYears', '0', 'Loan term'],
    ['loanTermYears', '101', 'Loan term'],
  ] as const)('rejects invalid %s values', (field, value, expected) => {
    expect(validateFeasibilityDraft({ ...valid, [field]: value })).toContain(
      expected,
    );
  });

  it('accepts exact API-compatible boundaries', () => {
    expect(validateFeasibilityDraft(valid)).toBeNull();
    expect(
      validateFeasibilityDraft({
        ...valid,
        annualInterestRate: '100.0000',
        loanTermYears: '100',
      }),
    ).toBeNull();
  });
});
