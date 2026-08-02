import { z } from 'zod';

function isNonNegativeDecimal(value: string) {
  return /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(value.trim());
}

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

export const taxCalculationSchema = z
  .object({
    grossTaxableIncome: z.string().trim(),
    manualAnnualNetIncome: z.string().trim(),
    manualJurisdiction: z.string().trim().max(50),
    manualTaxYear: z.string().trim().max(20),
    mode: z.enum(['AUTOMATIC', 'MANUAL_NET']),
    parameters: z.string(),
    providerYear: z.string(),
  })
  .superRefine((values, context) => {
    if (!isNonNegativeDecimal(values.grossTaxableIncome)) {
      context.addIssue({
        code: 'custom',
        message: 'Enter a non-negative gross taxable income',
        path: ['grossTaxableIncome'],
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
      return;
    }
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
    if (!isNonNegativeDecimal(values.manualAnnualNetIncome)) {
      context.addIssue({
        code: 'custom',
        message: 'Enter a non-negative annual net income',
        path: ['manualAnnualNetIncome'],
      });
    }
  });

export type TaxCalculationFields = z.infer<typeof taxCalculationSchema>;
