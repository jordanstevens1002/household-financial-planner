import { z } from 'zod';

function nonNegativeDecimal(value: string) {
  return /^(?:\d+(?:\.\d{0,2})?|\.\d{1,2})$/.test(value.trim());
}

export const expenseSchema = z
  .object({
    amount: z
      .string()
      .refine(
        nonNegativeDecimal,
        'Enter a non-negative amount with up to 2 decimals',
      ),
    annualGrowthRate: z.string().refine((value) => {
      if (value.trim() === '') return true;
      if (!/^-?(?:\d+(?:\.\d{0,4})?|\.\d{1,4})$/.test(value.trim())) {
        return false;
      }
      const rate = Number(value);
      return rate >= -100 && rate <= 100;
    }, 'Enter a rate from -100 to 100'),
    categoryId: z.string().uuid('Choose an expense category'),
    displayName: z.string().trim().min(1, 'Enter an expense name').max(200),
    effectiveFrom: z.iso.date('Enter a valid start date'),
    effectiveTo: z.union([z.literal(''), z.iso.date('Enter a valid end date')]),
    frequency: z.enum([
      'WEEKLY',
      'FORTNIGHTLY',
      'MONTHLY',
      'QUARTERLY',
      'ANNUAL',
      'ONCE',
    ]),
    isEssential: z.enum(['true', 'false']),
    notes: z.string().max(2000),
    personId: z.string(),
  })
  .refine(
    (fields) =>
      fields.effectiveTo === '' || fields.effectiveTo >= fields.effectiveFrom,
    {
      message: 'End date cannot be before start date',
      path: ['effectiveTo'],
    },
  )
  .refine(
    (fields) => fields.frequency !== 'ONCE' || fields.annualGrowthRate === '',
    {
      message: 'Growth does not apply to a one-off expense',
      path: ['annualGrowthRate'],
    },
  );

export type ExpenseFields = z.infer<typeof expenseSchema>;
