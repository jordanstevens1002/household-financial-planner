import { z } from 'zod';

const optionalDate = z
  .string()
  .refine((value) => value === '' || /^\d{4}-\d{2}-\d{2}$/.test(value), {
    message: 'Use YYYY-MM-DD',
  });

function isJsonObject(value: string) {
  try {
    const parsed: unknown = JSON.parse(value || '{}');
    return (
      typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
    );
  } catch {
    return false;
  }
}

export const taxProfileSchema = z
  .object({
    effectiveFrom: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Use YYYY-MM-DD'),
    effectiveTo: optionalDate,
    manualAnnualNetIncome: z.string().trim(),
    manualJurisdiction: z.string().trim().max(50),
    manualTaxYear: z.string().trim().max(20),
    mode: z.enum(['AUTOMATIC', 'MANUAL_NET']),
    parameters: z.string(),
    providerYear: z.string(),
  })
  .superRefine((values, context) => {
    if (values.effectiveTo && values.effectiveTo < values.effectiveFrom) {
      context.addIssue({
        code: 'custom',
        message: 'End date must not precede start date',
        path: ['effectiveTo'],
      });
    }
    if (values.mode === 'AUTOMATIC') {
      if (values.providerYear === '') {
        context.addIssue({
          code: 'custom',
          message: 'Choose an installed provider and tax year',
          path: ['providerYear'],
        });
      }
      if (!isJsonObject(values.parameters)) {
        context.addIssue({
          code: 'custom',
          message: 'Enter a JSON object',
          path: ['parameters'],
        });
      }
    }
    if (values.mode === 'MANUAL_NET') {
      if (values.manualJurisdiction.length < 2) {
        context.addIssue({
          code: 'custom',
          message: 'Enter a jurisdiction',
          path: ['manualJurisdiction'],
        });
      }
      if (values.manualTaxYear === '') {
        context.addIssue({
          code: 'custom',
          message: 'Enter a tax year',
          path: ['manualTaxYear'],
        });
      }
      if (
        values.manualAnnualNetIncome === '' ||
        !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(values.manualAnnualNetIncome)
      ) {
        context.addIssue({
          code: 'custom',
          message: 'Enter a non-negative annual net income',
          path: ['manualAnnualNetIncome'],
        });
      }
    }
  });

export type TaxProfileFields = z.infer<typeof taxProfileSchema>;

export function parseProviderParameters(
  value: string,
): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value || '{}');
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new TypeError('Provider settings must be a JSON object');
  }
  return parsed as Record<string, unknown>;
}
