import type { components } from '../../api/schema';

type Person = components['schemas']['PersonRead'];

export const MAX_SETUP_BORROWERS = 20;

export function isPersonActiveOn(person: Person, asOf: string) {
  return (
    person.is_active &&
    person.effective_from <= asOf &&
    (person.effective_to === null ||
      person.effective_to === undefined ||
      person.effective_to >= asOf)
  );
}

export function setupBorrowerLabel(person: Person, asOf: string) {
  return `${person.display_name}${isPersonActiveOn(person, asOf) ? '' : ' (inactive)'}`;
}

export function setupBorrowerOptionDisabled(
  selectedIds: string[],
  optionId: string,
) {
  return (
    selectedIds.length >= MAX_SETUP_BORROWERS && !selectedIds.includes(optionId)
  );
}
