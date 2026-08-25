import {
  isPersonActiveOn,
  MAX_SETUP_BORROWERS,
  setupBorrowerLabel,
  setupBorrowerOptionDisabled,
} from './propertySetupBorrowers';

const person = {
  date_of_birth: null,
  display_name: 'Alex',
  effective_from: '2026-01-01',
  effective_to: null,
  household_id: 'dccc2857-cf74-4863-9f00-c99a9f815495',
  id: '8a76ff72-b719-4ca9-9f77-b66f901fb56f',
  is_active: true,
  legal_name: null,
  notes: null,
  tax_jurisdiction: null,
};

describe('property setup borrowers', () => {
  it('resolves activity against both effective dates and the active flag', () => {
    expect(isPersonActiveOn(person, '2026-01-01')).toBe(true);
    expect(isPersonActiveOn(person, '2025-12-31')).toBe(false);
    expect(
      isPersonActiveOn({ ...person, effective_to: '2026-06-30' }, '2026-06-30'),
    ).toBe(true);
    expect(
      isPersonActiveOn({ ...person, effective_to: '2026-06-30' }, '2026-07-01'),
    ).toBe(false);
    expect(
      isPersonActiveOn({ ...person, is_active: false }, '2026-01-01'),
    ).toBe(false);
  });

  it('labels future and expired people inactive for the position date', () => {
    expect(setupBorrowerLabel(person, '2025-12-31')).toBe('Alex (inactive)');
    expect(
      setupBorrowerLabel(
        { ...person, effective_to: '2026-06-30' },
        '2026-07-01',
      ),
    ).toBe('Alex (inactive)');
    expect(setupBorrowerLabel(person, '2026-01-01')).toBe('Alex');
  });

  it('prevents a new selection at the limit without disabling selected people', () => {
    const selectedIds = Array.from(
      { length: MAX_SETUP_BORROWERS },
      (_, index) => `person-${index}`,
    );
    expect(setupBorrowerOptionDisabled(selectedIds, 'person-new')).toBe(true);
    expect(setupBorrowerOptionDisabled(selectedIds, 'person-0')).toBe(false);
    expect(
      setupBorrowerOptionDisabled(selectedIds.slice(1), 'person-new'),
    ).toBe(false);
  });
});
