import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Button,
  CircularProgress,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { useForm, useWatch } from 'react-hook-form';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { useAuth } from '../auth/AuthContext';
import {
  taxCalculationSchema,
  type TaxCalculationFields,
} from './taxCalculationValidation';
import { parseProviderParameters } from './taxProfileValidation';

type Calculation = components['schemas']['TaxCalculationRead'];
type Component = components['schemas']['TaxComponentRead'];
type Provider = components['schemas']['TaxProviderRead'];

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function splitProvider(value: string): [string, string] {
  const separator = value.indexOf('|');
  return [value.slice(0, separator), value.slice(separator + 1)];
}

function formatAmount(value: number | string) {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(Number(value));
}

export function TaxCalculatorPanel() {
  const auth = useAuth();
  const providers = useQuery({
    queryFn: () => apiRequest<Provider[]>('/api/v1/tax-providers'),
    queryKey: ['providers', 'tax'],
    retry: false,
  });
  const providerOptions = useMemo(
    () =>
      (providers.data ?? []).flatMap((provider) =>
        provider.supported_tax_years.map((taxYear) => ({
          jurisdiction: provider.jurisdiction,
          label: `${provider.display_name} — ${taxYear}`,
          taxYear,
          value: `${provider.jurisdiction}|${taxYear}`,
        })),
      ),
    [providers.data],
  );
  const form = useForm<TaxCalculationFields>({
    defaultValues: {
      grossTaxableIncome: '',
      manualAnnualNetIncome: '',
      manualJurisdiction: '',
      manualTaxYear: '',
      mode: 'AUTOMATIC',
      parameters: '{}',
      providerYear: '',
    },
    resolver: zodResolver(taxCalculationSchema),
  });
  const mode = useWatch({ control: form.control, name: 'mode' });
  const calculate = useMutation({
    mutationFn: (fields: TaxCalculationFields) => {
      const automatic = fields.mode === 'AUTOMATIC';
      const [jurisdiction, taxYear] = automatic
        ? splitProvider(fields.providerYear)
        : [fields.manualJurisdiction.toUpperCase(), fields.manualTaxYear];
      return apiRequest<Calculation>('/api/v1/calculations/tax', {
        body: JSON.stringify({
          gross_taxable_income: fields.grossTaxableIncome,
          jurisdiction,
          settings: automatic
            ? {
                calculation_mode: 'AUTOMATIC',
                parameters: parseProviderParameters(fields.parameters),
              }
            : {
                calculation_mode: 'MANUAL_NET',
                manual_annual_net_income: fields.manualAnnualNetIncome,
              },
          tax_year: taxYear,
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      });
    },
  });
  const result = calculate.data;
  const providerName = result
    ? providers.data?.find(
        (provider) => provider.jurisdiction === result.jurisdiction,
      )?.display_name
    : undefined;
  const columns: DataColumn<Component>[] = [
    { key: 'component', label: 'Component', render: (row) => row.display_name },
    {
      key: 'amount',
      label: 'Amount',
      render: (row) => formatAmount(row.amount),
    },
  ];

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        This standalone estimate does not save or change household records. It
        is an indicative calculation, not financial or tax advice.
      </Alert>
      {providers.error ? (
        <Alert
          action={
            <Button
              color="inherit"
              onClick={() => void providers.refetch()}
              size="small"
            >
              Retry
            </Button>
          }
          severity="warning"
        >
          Installed tax providers could not be loaded. Manual net-income mode
          remains available. {message(providers.error)}
        </Alert>
      ) : null}
      <form
        onSubmit={(event) =>
          void form.handleSubmit((fields) => calculate.mutate(fields))(event)
        }
      >
        <Stack spacing={2}>
          <TextField
            defaultValue="AUTOMATIC"
            label="Calculation method"
            select
            {...form.register('mode')}
          >
            <MenuItem value="AUTOMATIC">Installed tax provider</MenuItem>
            <MenuItem value="MANUAL_NET">Manual annual net income</MenuItem>
          </TextField>
          <TextField
            error={Boolean(form.formState.errors.grossTaxableIncome)}
            helperText={form.formState.errors.grossTaxableIncome?.message}
            label="Gross taxable income"
            {...form.register('grossTaxableIncome')}
          />
          {mode === 'AUTOMATIC' ? (
            <>
              {providers.isPending ? (
                <CircularProgress
                  aria-label="Loading tax providers"
                  size={24}
                />
              ) : providerOptions.length ? (
                <TextField
                  defaultValue=""
                  error={Boolean(form.formState.errors.providerYear)}
                  helperText={form.formState.errors.providerYear?.message}
                  label="Provider and tax year"
                  select
                  {...form.register('providerYear')}
                >
                  {providerOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>
              ) : (
                <Alert severity="warning">
                  No installed provider years are available. Choose manual
                  annual net income or install a provider.
                </Alert>
              )}
              <AdvancedSection description="Provider-specific inputs are optional and vary by the installed tax engine.">
                <TextField
                  error={Boolean(form.formState.errors.parameters)}
                  fullWidth
                  helperText={form.formState.errors.parameters?.message}
                  label="Provider settings as JSON"
                  minRows={3}
                  multiline
                  {...form.register('parameters')}
                />
              </AdvancedSection>
            </>
          ) : (
            <>
              <TextField
                error={Boolean(form.formState.errors.manualJurisdiction)}
                helperText={form.formState.errors.manualJurisdiction?.message}
                label="Jurisdiction"
                {...form.register('manualJurisdiction')}
              />
              <TextField
                error={Boolean(form.formState.errors.manualTaxYear)}
                helperText={form.formState.errors.manualTaxYear?.message}
                label="Tax year"
                {...form.register('manualTaxYear')}
              />
              <TextField
                error={Boolean(form.formState.errors.manualAnnualNetIncome)}
                helperText={
                  form.formState.errors.manualAnnualNetIncome?.message
                }
                label="Annual net income"
                {...form.register('manualAnnualNetIncome')}
              />
            </>
          )}
          {calculate.error ? (
            <Alert severity="error">
              Could not calculate tax. {message(calculate.error)}
            </Alert>
          ) : null}
          <Button
            disabled={
              calculate.isPending ||
              (mode === 'AUTOMATIC' &&
                (providers.isPending || providerOptions.length === 0))
            }
            sx={{ alignSelf: 'flex-start' }}
            type="submit"
            variant="contained"
          >
            Calculate estimate
          </Button>
        </Stack>
      </form>
      {result ? (
        <Paper
          aria-label="Tax estimate result"
          sx={{ p: 2 }}
          variant="outlined"
        >
          <Stack spacing={2}>
            <Typography variant="h2">Estimated result</Typography>
            <Typography>
              Provider:{' '}
              {providerName ??
                `${result.jurisdiction} (not currently discovered)`}
              {' · '}Tax year: {result.tax_year}
              {' · '}Ruleset: {result.ruleset_version}
            </Typography>
            <Typography>
              Taxable income: {formatAmount(result.taxable_income)}
            </Typography>
            <Typography>
              Tax and repayments: {formatAmount(result.total)}
            </Typography>
            <Typography>
              Net income: {formatAmount(result.net_income)}
            </Typography>
            {result.warnings.map((warning) => (
              <Alert key={warning} severity="warning">
                {warning}
              </Alert>
            ))}
            {result.components.length ? (
              <DataTable
                caption="Tax estimate components"
                columns={columns}
                getRowKey={(row) => row.code}
                rows={result.components}
              />
            ) : (
              <Typography color="text.secondary">
                No component breakdown is available for this calculation.
              </Typography>
            )}
          </Stack>
        </Paper>
      ) : null}
    </Stack>
  );
}
