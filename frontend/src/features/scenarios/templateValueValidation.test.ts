import { describe, expect, it } from 'vitest';

import { validateTemplateValue } from './templateValueValidation';

describe('scenario template value validation', () => {
  it.each([
    ['HIGHER_EXPENSES', '0'],
    ['HIGHER_EXPENSES', '1000'],
    ['LOWER_INCOME', '-100'],
    ['LOWER_INCOME', '0'],
    ['DELAYED_PROPERTY_PURCHASE', '3650'],
    ['EARLIER_PROPERTY_PURCHASE', '-3650'],
    ['MAJOR_MAINTENANCE_COST', '9999999999999999.99'],
  ])('accepts the %s boundary value %s', (code, value) => {
    expect(validateTemplateValue(code, value)).toBe('');
  });

  it.each([
    ['HIGHER_EXPENSES', '-1'],
    ['HIGHER_EXPENSES', '1000.0001'],
    ['LOWER_INCOME', '1'],
    ['DELAYED_PROPERTY_PURCHASE', '-1'],
    ['DELAYED_PROPERTY_PURCHASE', '1.5'],
    ['DELAYED_PROPERTY_PURCHASE', '3651'],
    ['MAJOR_MAINTENANCE_COST', '9999999999999999.999'],
    ['HIGHER_INTEREST_RATES', '1e6'],
    ['HIGHER_INTEREST_RATES', 'not-a-number'],
  ])('rejects the %s value %s', (code, value) => {
    expect(validateTemplateValue(code, value)).not.toBe('');
  });
});
