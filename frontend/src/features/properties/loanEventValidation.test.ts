import { describe, expect, it } from 'vitest';

import {
  eventDisplayName,
  type LoanEventDraft,
  validateLoanEvent,
  valueKind,
} from './loanEventValidation';

const draft: LoanEventDraft = {
  amount: '100',
  classification: 'OBSERVED',
  effectiveAt: '2027-01-01T12:00',
  eventTypeId: 'event-type',
  idempotencyKey: '',
  notes: '',
  percentage: '5.5',
  termMonths: '240',
};

describe('loan event validation', () => {
  it.each([
    [{ eventTypeId: '' }, 'LOAN_RATE_CHANGED', 'Choose a loan event type'],
    [
      { effectiveAt: '' },
      'LOAN_RATE_CHANGED',
      'Choose when the change takes effect',
    ],
    [
      { percentage: '' },
      'LOAN_RATE_CHANGED',
      'Enter a rate from 0 to 100 percent',
    ],
    [
      { percentage: '100.1' },
      'LOAN_RATE_CHANGED',
      'Enter a rate from 0 to 100 percent',
    ],
    [{ amount: '-1' }, 'LOAN_REDRAWN', 'Enter a non-negative amount'],
    [
      { termMonths: '12.5' },
      'LOAN_TERM_CHANGED',
      'Enter a positive whole number of months',
    ],
    [
      { notes: 'x'.repeat(2_001) },
      'LOAN_CLOSED',
      'Notes must be 2,000 characters or fewer',
    ],
    [
      { idempotencyKey: 'x'.repeat(101) },
      'LOAN_CLOSED',
      'Idempotency key must be 100 characters or fewer',
    ],
  ])('rejects invalid input %#', (changes, code, expected) => {
    expect(validateLoanEvent({ ...draft, ...changes }, code)).toBe(expected);
  });

  it('identifies event value controls and friendly labels', () => {
    expect(valueKind('LOAN_RATE_CHANGED')).toBe('percentage');
    expect(valueKind('LOAN_REPAYMENT_CHANGED')).toBe('amount');
    expect(valueKind('LOAN_TERM_CHANGED')).toBe('term');
    expect(valueKind('LOAN_INTEREST_ONLY_STARTED')).toBe('none');
    expect(eventDisplayName('LOAN_LUMP_SUM_PAID')).toBe('Lump Sum Paid');
  });
});
