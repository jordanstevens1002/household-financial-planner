import { describe, expect, it } from 'vitest';

import {
  personActiveForOverride,
  type RepaymentAllocationDraft,
  validateRepaymentOverride,
} from './repaymentOverrideValidation';

const person = {
  date_of_birth: null,
  display_name: 'Alex',
  effective_from: '2020-01-01',
  effective_to: null,
  household_id: '1bfbb15e-5293-4e29-95e0-f86b82e62528',
  id: 'a2342535-475d-4eb9-9257-acfdf704bb65',
  is_active: true,
};
const allocation: RepaymentAllocationDraft = {
  notes: '',
  percentage: '100',
  personId: person.id,
};

function validate(
  overrides: Partial<Parameters<typeof validateRepaymentOverride>[0]> = {},
) {
  return validateRepaymentOverride({
    allocations: [allocation],
    effectiveFrom: '2026-01-01',
    effectiveTo: '',
    existingStartDates: [],
    people: [person],
    ...overrides,
  });
}

describe('repayment override validation', () => {
  it.each([
    [{ effectiveFrom: '' }, 'Choose when this override begins'],
    [
      { effectiveTo: '2025-12-31' },
      'The end date cannot precede the start date',
    ],
    [
      { existingStartDates: ['2026-01-01'] },
      'An override already begins on this date',
    ],
    [
      { allocations: [{ ...allocation, notes: 'x'.repeat(2_001) }] },
      'Notes must be 2,000 characters or fewer',
    ],
    [
      { allocations: [{ ...allocation, personId: '' }] },
      'Choose a different person for each allocation',
    ],
    [
      { allocations: [allocation, allocation] },
      'Choose a different person for each allocation',
    ],
    [
      { allocations: [{ ...allocation, percentage: '100.001' }] },
      'Enter each percentage from 0.01 to 100',
    ],
    [
      { allocations: [{ ...allocation, percentage: '99.99' }] },
      'Repayment allocations must total exactly 100%',
    ],
    [
      { people: [{ ...person, is_active: false }] },
      'Each person must be active for the complete override period',
    ],
    [
      { people: [{ ...person, effective_from: '2026-02-01' }] },
      'Each person must be active for the complete override period',
    ],
    [
      {
        effectiveTo: '2026-06-30',
        people: [{ ...person, effective_to: '2026-05-31' }],
      },
      'Each person must be active for the complete override period',
    ],
  ])('rejects invalid input %#', (overrides, expected) => {
    expect(validate(overrides)).toBe(expected);
  });

  it('accepts exact decimal allocations for active people', () => {
    expect(
      validate({
        allocations: [
          { ...allocation, percentage: '33.33' },
          { ...allocation, percentage: '66.67', personId: 'second' },
        ],
        people: [person, { ...person, id: 'second' }],
      }),
    ).toBeNull();
  });

  it('evaluates activity across the complete interval', () => {
    expect(personActiveForOverride(person, '2026-01-01', '')).toBe(true);
    expect(
      personActiveForOverride(
        { ...person, effective_to: '2026-06-30' },
        '2026-01-01',
        '2026-06-30',
      ),
    ).toBe(true);
    expect(
      personActiveForOverride(
        { ...person, effective_to: '2026-06-30', is_active: false },
        '2026-01-01',
        '2026-06-30',
      ),
    ).toBe(true);
    expect(
      personActiveForOverride(
        { ...person, effective_to: '2026-06-30', is_active: false },
        '2026-01-01',
        '',
      ),
    ).toBe(false);
  });
});
