import {
  loadSelection,
  saveSelection,
  selectionKeys,
} from './selectionStorage';

const id = '2f35e046-bf6e-4555-871d-a7514cbac147';

describe('selection storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('persists only a selected entity identifier', () => {
    saveSelection('household', id);

    expect(loadSelection('household')).toBe(id);
    expect(localStorage).toHaveLength(1);
    expect(localStorage.getItem(selectionKeys.household)).toBe(id);
  });

  it('clears a selection and ignores malformed stored data', () => {
    localStorage.setItem(selectionKeys.person, 'not-an-identifier');
    expect(loadSelection('person')).toBeNull();

    saveSelection('person', id);
    saveSelection('person', null);
    expect(loadSelection('person')).toBeNull();
  });

  it('rejects values other than UUID identifiers', () => {
    expect(() => {
      saveSelection('property', 'session-token');
    }).toThrow();
  });
});
