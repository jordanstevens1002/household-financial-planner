function finiteAmount(value: number | string): number {
  const amount = typeof value === 'string' ? Number(value) : value;
  if (!Number.isFinite(amount)) {
    throw new TypeError('Amount must be a finite number');
  }
  return amount;
}

export function formatCurrency(
  value: number | string,
  currency: string,
  locale?: string,
): string {
  return new Intl.NumberFormat(locale, {
    currency,
    style: 'currency',
  }).format(finiteAmount(value));
}

export function formatDate(value: string | Date, locale?: string): string {
  const date =
    typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
      ? new Date(`${value}T00:00:00Z`)
      : new Date(value);

  if (Number.isNaN(date.getTime())) {
    throw new TypeError('Date must be valid');
  }

  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
    year: 'numeric',
  }).format(date);
}
