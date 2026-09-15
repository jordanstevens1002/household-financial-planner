import type { components } from '../../api/schema';

type Person = components['schemas']['PersonRead'];

export interface RepaymentAllocationDraft {
  notes: string;
  percentage: string;
  personId: string;
}

export function personActiveForOverride(
  person: Person,
  effectiveFrom: string,
  effectiveTo: string,
) {
  const coversDates =
    person.effective_from <= effectiveFrom &&
    (person.effective_to == null ||
      person.effective_to >= (effectiveTo || effectiveFrom));
  if (!coversDates) return false;
  if (person.is_active) return true;
  return Boolean(
    effectiveTo && person.effective_to && person.effective_to >= effectiveTo,
  );
}

function percentageHundredths(value: string): number | null {
  const match = /^(\d{1,3})(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match) return null;
  const result =
    Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0'));
  return result > 0 && result <= 10_000 ? result : null;
}

export function validateRepaymentOverride({
  allocations,
  effectiveFrom,
  effectiveTo,
  existingStartDates,
  people,
}: {
  allocations: RepaymentAllocationDraft[];
  effectiveFrom: string;
  effectiveTo: string;
  existingStartDates: string[];
  people: Person[];
}): string | null {
  if (!effectiveFrom) return 'Choose when this override begins';
  if (effectiveTo && effectiveTo < effectiveFrom)
    return 'The end date cannot precede the start date';
  if (existingStartDates.includes(effectiveFrom))
    return 'An override already begins on this date';
  if (allocations.some((item) => item.notes.length > 2_000))
    return 'Notes must be 2,000 characters or fewer';
  const personIds = allocations.map((item) => item.personId);
  if (
    personIds.some((id) => !id) ||
    new Set(personIds).size !== personIds.length
  )
    return 'Choose a different person for each allocation';
  const percentages = allocations.map((item) =>
    percentageHundredths(item.percentage),
  );
  if (percentages.some((value) => value == null))
    return 'Enter each percentage from 0.01 to 100';
  if (
    percentages.reduce<number>((total, value) => total + (value ?? 0), 0) !==
    10_000
  )
    return 'Repayment allocations must total exactly 100%';
  if (
    allocations.some((item) => {
      const person = people.find((candidate) => candidate.id === item.personId);
      return (
        person == null ||
        !personActiveForOverride(person, effectiveFrom, effectiveTo)
      );
    })
  )
    return 'Each person must be active for the complete override period';
  return null;
}
