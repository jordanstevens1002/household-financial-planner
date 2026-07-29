import { z } from 'zod';

const identifier = z.uuid();

export const selectionKeys = {
  household: 'hfp.selection.household',
  person: 'hfp.selection.person',
  property: 'hfp.selection.property',
} as const;

export type SelectionType = keyof typeof selectionKeys;

export function loadSelection(
  type: SelectionType,
  storage: Pick<Storage, 'getItem'> = localStorage,
): string | null {
  const value = storage.getItem(selectionKeys[type]);
  const result = identifier.safeParse(value);
  return result.success ? result.data : null;
}

export function saveSelection(
  type: SelectionType,
  value: string | null,
  storage: Pick<Storage, 'removeItem' | 'setItem'> = localStorage,
): void {
  const key = selectionKeys[type];
  if (value === null) {
    storage.removeItem(key);
    return;
  }

  storage.setItem(key, identifier.parse(value));
}
