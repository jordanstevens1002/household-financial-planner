import type { components } from '../../api/schema';

export const LOAN_EVENT_CODES = [
  'LOAN_RATE_CHANGED',
  'LOAN_REPAYMENT_CHANGED',
  'LOAN_LUMP_SUM_PAID',
  'LOAN_OFFSET_CHANGED',
  'LOAN_REDRAWN',
  'LOAN_TERM_CHANGED',
  'LOAN_INTEREST_ONLY_STARTED',
  'LOAN_INTEREST_ONLY_ENDED',
] as const;

export type LoanEventCode = (typeof LOAN_EVENT_CODES)[number];
type Classification = components['schemas']['EventClassification'];

export interface LoanEventDraft {
  amount: string;
  classification: Classification;
  effectiveAt: string;
  eventTypeId: string;
  idempotencyKey: string;
  notes: string;
  percentage: string;
  termMonths: string;
}

const AMOUNT_CODES = new Set<LoanEventCode>([
  'LOAN_REPAYMENT_CHANGED',
  'LOAN_LUMP_SUM_PAID',
  'LOAN_OFFSET_CHANGED',
  'LOAN_REDRAWN',
]);

function validDecimal(value: string, decimalPlaces: number, maxDigits: number) {
  if (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)) return false;
  const [whole = '', fraction = ''] = value.split('.');
  return (
    fraction.length <= decimalPlaces &&
    whole.length + fraction.length <= maxDigits
  );
}

export function utcInstant(value: string) {
  return new Date(`${value}Z`).toISOString();
}

export function valueKind(code: string) {
  if (code === 'LOAN_RATE_CHANGED') return 'percentage';
  if (code === 'LOAN_TERM_CHANGED') return 'term';
  if (AMOUNT_CODES.has(code as LoanEventCode)) return 'amount';
  return 'none';
}

export function validateLoanEvent(draft: LoanEventDraft, code: string) {
  if (!draft.eventTypeId) return 'Choose a loan event type';
  if (!draft.effectiveAt) return 'Choose when the change takes effect';
  if (draft.notes.length > 2_000)
    return 'Notes must be 2,000 characters or fewer';
  if (draft.idempotencyKey.length > 100)
    return 'Idempotency key must be 100 characters or fewer';
  if (valueKind(code) === 'amount') {
    if (!validDecimal(draft.amount.trim(), 2, 18))
      return 'Enter a non-negative amount with up to 18 digits and 2 decimal places';
  }
  if (valueKind(code) === 'percentage') {
    const percentage = Number(draft.percentage);
    if (
      !validDecimal(draft.percentage.trim(), 4, 7) ||
      !Number.isFinite(percentage) ||
      percentage < 0 ||
      percentage > 100
    )
      return 'Enter a rate from 0 to 100 percent with up to 4 decimal places';
  }
  if (
    valueKind(code) === 'term' &&
    (!/^\d+$/.test(draft.termMonths) ||
      Number(draft.termMonths) < 1 ||
      Number(draft.termMonths) > 1_200)
  )
    return 'Enter a whole number of months from 1 to 1,200';
  return null;
}

export function eventDisplayName(code: string) {
  return code
    .replace(/^LOAN_/, '')
    .split('_')
    .map((word) => `${word[0]}${word.slice(1).toLowerCase()}`)
    .join(' ');
}
