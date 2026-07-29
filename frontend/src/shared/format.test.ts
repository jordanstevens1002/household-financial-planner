import { formatCurrency, formatDate } from './format';

describe('formatting helpers', () => {
  it('formats an explicitly supplied currency without a country default', () => {
    expect(formatCurrency('1234.5', 'NZD', 'en-NZ')).toBe('$1,234.50');
    expect(formatCurrency(1234.5, 'EUR', 'de-DE')).toContain('1.234,50');
  });

  it('formats date-only values without shifting the calendar date', () => {
    expect(formatDate('2026-07-29', 'en-AU')).toBe('29 July 2026');
  });

  it('rejects invalid values', () => {
    expect(() => formatCurrency('many', 'USD')).toThrow(
      'Amount must be a finite number',
    );
    expect(() => formatDate('not-a-date')).toThrow('Date must be valid');
  });
});
