import { z } from 'zod';

const optionalDate = z
  .string()
  .refine((value) => value === '' || /^\d{4}-\d{2}-\d{2}$/.test(value), {
    message: 'Use YYYY-MM-DD',
  });

function optionalDecimal(
  minimum: number,
  maximum: number | undefined,
  places: number,
) {
  const pattern = new RegExp(
    `^-?(?:\\d+(?:\\.\\d{0,${places}})?|\\.\\d{1,${places}})$`,
  );
  return z
    .string()
    .trim()
    .refine(
      (value) =>
        value === '' ||
        (pattern.test(value) &&
          Number(value) >= minimum &&
          (maximum === undefined || Number(value) <= maximum)),
      {
        message:
          maximum === undefined
            ? `Enter a number of ${minimum} or more`
            : `Enter a number from ${minimum} to ${maximum}`,
      },
    );
}

export const incomeSchema = z
  .object({
    annualGrowthRate: optionalDecimal(-100, 100, 4),
    displayName: z.string().trim().min(1, 'Enter a name').max(200),
    effectiveFrom: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Use YYYY-MM-DD'),
    effectiveTo: optionalDate,
    frequency: z.enum([
      'WEEKLY',
      'FORTNIGHTLY',
      'MONTHLY',
      'QUARTERLY',
      'ANNUAL',
    ]),
    grossAmount: z
      .string()
      .trim()
      .min(1, 'Enter a gross amount')
      .regex(
        /^(?:\d+(?:\.\d{0,2})?|\.\d{1,2})$/,
        'Enter a non-negative amount with up to 2 decimal places',
      ),
    incomeTypeId: z.string().min(1, 'Choose an income type'),
    notes: z.string().max(2000),
    salarySacrificeAmount: optionalDecimal(0, undefined, 2),
    taxable: z.enum(['true', 'false']),
  })
  .refine(
    ({ effectiveFrom, effectiveTo }) =>
      effectiveTo === '' || effectiveTo >= effectiveFrom,
    { message: 'End date must not precede start date', path: ['effectiveTo'] },
  );

export type IncomeFields = z.infer<typeof incomeSchema>;
