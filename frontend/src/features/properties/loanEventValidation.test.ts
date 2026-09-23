import { describe, expect, it, vi } from 'vitest';

import {
  eventDisplayName,
  type LoanEventDraft,
  utcInstant,
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
      'Enter a rate from 0 to 100 percent with up to 4 decimal places',
    ],
    [
      { percentage: '100.1' },
      'LOAN_RATE_CHANGED',
      'Enter a rate from 0 to 100 percent with up to 4 decimal places',
    ],
    [
      { percentage: '1.12345' },
      'LOAN_RATE_CHANGED',
      'Enter a rate from 0 to 100 percent with up to 4 decimal places',
    ],
    [
      { amount: '-1' },
      'LOAN_REDRAWN',
      'Enter a non-negative amount with up to 18 digits and 2 decimal places',
    ],
    [
      { amount: '1e3' },
      'LOAN_REDRAWN',
      'Enter a non-negative amount with up to 18 digits and 2 decimal places',
    ],
    [
      { amount: '1.234' },
      'LOAN_REDRAWN',
      'Enter a non-negative amount with up to 18 digits and 2 decimal places',
    ],
    [
      { termMonths: '12.5' },
      'LOAN_TERM_CHANGED',
      'Enter a whole number of months from 1 to 1,200',
    ],
    [
      { termMonths: '1201' },
      'LOAN_TERM_CHANGED',
      'Enter a whole number of months from 1 to 1,200',
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

  it('accepts values at the API decimal and term boundaries', () => {
    expect(
      validateLoanEvent(
        { ...draft, amount: '9999999999999999.99' },
        'LOAN_REDRAWN',
      ),
    ).toBeNull();
    expect(
      validateLoanEvent(
        { ...draft, percentage: '100.0000' },
        'LOAN_RATE_CHANGED',
      ),
    ).toBeNull();
    expect(
      validateLoanEvent({ ...draft, termMonths: '1200' }, 'LOAN_TERM_CHANGED'),
    ).toBeNull();
  });

  it('treats the entered date and time as UTC in a non-UTC timezone', () => {
    vi.stubEnv('TZ', 'Australia/Sydney');
    expect(utcInstant('2027-01-02T00:30')).toBe('2027-01-02T00:30:00.000Z');
    vi.unstubAllEnvs();
  });
});
