interface Rule {
  decimalPlaces: number;
  maximum: string;
  minimum: string;
}

const rules: Record<string, Rule> = {
  DELAYED_PROPERTY_PURCHASE: {
    decimalPlaces: 0,
    maximum: '3650',
    minimum: '0',
  },
  EARLIER_PROPERTY_PURCHASE: {
    decimalPlaces: 0,
    maximum: '0',
    minimum: '-3650',
  },
  HIGHER_EXPENSES: { decimalPlaces: 4, maximum: '1000', minimum: '0' },
  HIGHER_INTEREST_RATES: { decimalPlaces: 4, maximum: '100', minimum: '0' },
  HIGHER_PROPERTY_GROWTH: { decimalPlaces: 4, maximum: '100', minimum: '0' },
  LOWER_INCOME: { decimalPlaces: 4, maximum: '0', minimum: '-100' },
  LOWER_PROPERTY_GROWTH: { decimalPlaces: 4, maximum: '0', minimum: '-100' },
  MAJOR_MAINTENANCE_COST: {
    decimalPlaces: 2,
    maximum: '9999999999999999.99',
    minimum: '0',
  },
  PROPERTY_VACANT: { decimalPlaces: 2, maximum: '0', minimum: '0' },
  RETIREMENT_CONTRIBUTION_CHANGE: {
    decimalPlaces: 4,
    maximum: '1000',
    minimum: '-100',
  },
};

export function validateTemplateValue(code: string, rawValue: string): string {
  const rule = rules[code];
  if (!rule) return 'This template does not accept a configurable value.';
  const pattern = new RegExp(
    rule.decimalPlaces === 0
      ? '^-?(?:0|[1-9]\\d*)$'
      : `^-?(?:0|[1-9]\\d*)(?:\\.\\d{1,${rule.decimalPlaces}})?$`,
  );
  if (!pattern.test(rawValue.trim()))
    return rule.decimalPlaces === 0
      ? 'Template value must be a whole number.'
      : `Template value must be a plain decimal with at most ${rule.decimalPlaces} decimal places.`;
  const scaled = (value: string) => {
    const negative = value.startsWith('-');
    const [whole, fraction = ''] = value.replace('-', '').split('.');
    const magnitude = BigInt(
      `${whole}${fraction.padEnd(rule.decimalPlaces, '0')}`,
    );
    return negative ? -magnitude : magnitude;
  };
  const value = scaled(rawValue.trim());
  if (value < scaled(rule.minimum) || value > scaled(rule.maximum))
    return `Template value must be from ${rule.minimum} to ${rule.maximum}.`;
  return '';
}
