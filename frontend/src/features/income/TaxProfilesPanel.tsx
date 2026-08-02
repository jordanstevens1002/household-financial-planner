import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';
import {
  parseProviderParameters,
  taxProfileSchema,
  type TaxProfileFields,
} from './taxProfileValidation';

type Profile = components['schemas']['TaxProfileRead'];
type Provider = components['schemas']['TaxProviderRead'];

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function splitProvider(value: string): [string, string] {
  const separator = value.indexOf('|');
  return [value.slice(0, separator), value.slice(separator + 1)];
}

export function TaxProfilesPanel({
  canEdit,
  personId,
}: {
  canEdit: boolean;
  personId: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [createOpen, setCreateOpen] = useState(false);
  const profiles = useQuery({
    queryFn: () =>
      apiRequest<Profile[]>(`/api/v1/people/${personId}/tax-profiles`),
    queryKey: ['tax-profiles', personId],
    retry: false,
  });
  const providers = useQuery({
    queryFn: () => apiRequest<Provider[]>('/api/v1/tax-providers'),
    queryKey: ['providers', 'tax'],
    retry: false,
  });
  const providerOptions = useMemo(
    () =>
      (providers.data ?? []).flatMap((provider) =>
        provider.supported_tax_years.map((taxYear) => ({
          label: `${provider.display_name} — ${taxYear}`,
          value: `${provider.jurisdiction}|${taxYear}`,
        })),
      ),
    [providers.data],
  );
  const form = useForm<TaxProfileFields>({
    defaultValues: {
      effectiveFrom: localCalendarDate(),
      effectiveTo: '',
      manualAnnualNetIncome: '',
      manualJurisdiction: '',
      manualTaxYear: '',
      mode: 'AUTOMATIC',
      parameters: '{}',
      providerYear: '',
    },
    resolver: zodResolver(taxProfileSchema),
  });
  const mode = useWatch({ control: form.control, name: 'mode' });
  const createProfile = useMutation({
    mutationFn: (fields: TaxProfileFields) => {
      const automatic = fields.mode === 'AUTOMATIC';
      const [jurisdiction, taxYear] = automatic
        ? splitProvider(fields.providerYear)
        : [fields.manualJurisdiction.toUpperCase(), fields.manualTaxYear];
      return apiRequest<Profile>(`/api/v1/people/${personId}/tax-profiles`, {
        body: JSON.stringify({
          effective_from: fields.effectiveFrom,
          effective_to: fields.effectiveTo || null,
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
    onSuccess: (created) => {
      queryClient.setQueryData<Profile[]>(
        ['tax-profiles', personId],
        (current) => [...(current ?? []), created],
      );
      setCreateOpen(false);
      form.reset({
        effectiveFrom: localCalendarDate(),
        effectiveTo: '',
        manualAnnualNetIncome: '',
        manualJurisdiction: '',
        manualTaxYear: '',
        mode: 'AUTOMATIC',
        parameters: '{}',
        providerYear: '',
      });
      notify('Tax settings saved', 'success');
    },
  });
  const providerName = (jurisdiction: string) =>
    providers.data?.find((provider) => provider.jurisdiction === jurisdiction)
      ?.display_name ?? jurisdiction;
  const columns: DataColumn<Profile>[] = [
    {
      key: 'provider',
      label: 'Provider or jurisdiction',
      render: (row) =>
        row.settings.calculation_mode === 'MANUAL_NET'
          ? row.jurisdiction
          : providerName(row.jurisdiction),
    },
    { key: 'year', label: 'Tax year', render: (row) => row.tax_year },
    {
      key: 'method',
      label: 'Method',
      render: (row) =>
        row.settings.calculation_mode === 'MANUAL_NET'
          ? 'Manual annual net income'
          : 'Installed provider',
    },
    {
      key: 'effective',
      label: 'Effective from',
      render: (row) => formatDate(row.effective_from),
    },
  ];

  return (
    <Stack spacing={2}>
      {!canEdit ? (
        <Alert severity="info">
          You have view-only access to this person's tax settings.
        </Alert>
      ) : (
        <Button
          onClick={() => setCreateOpen(true)}
          sx={{ alignSelf: 'flex-start' }}
          variant="contained"
        >
          Add tax settings
        </Button>
      )}
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
      {profiles.isPending ? (
        <CircularProgress aria-label="Loading tax settings" />
      ) : profiles.error ? (
        <Alert severity="error">
          Could not load tax settings. {message(profiles.error)}
        </Alert>
      ) : profiles.data?.length ? (
        <DataTable
          caption="Tax settings"
          columns={columns}
          getRowKey={(row) => row.id}
          rows={profiles.data}
        />
      ) : (
        <EmptyState
          description="Choose an installed provider and year, or record a manual annual net income."
          title="No tax settings yet"
        />
      )}

      <Dialog fullWidth open={createOpen} onClose={() => setCreateOpen(false)}>
        <DialogTitle>Add tax settings</DialogTitle>
        <form
          onSubmit={(event) =>
            void form.handleSubmit((fields) => createProfile.mutate(fields))(
              event,
            )
          }
        >
          <DialogContent>
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
                  <AdvancedSection description="Provider-specific JSON is optional and should normally stay at its default.">
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
                    helperText={
                      form.formState.errors.manualJurisdiction?.message
                    }
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
              <TextField
                error={Boolean(form.formState.errors.effectiveFrom)}
                helperText={form.formState.errors.effectiveFrom?.message}
                label="Effective from"
                {...form.register('effectiveFrom')}
              />
              <TextField
                error={Boolean(form.formState.errors.effectiveTo)}
                helperText={form.formState.errors.effectiveTo?.message}
                label="Effective to (optional)"
                {...form.register('effectiveTo')}
              />
              {createProfile.error ? (
                <Alert severity="error">{message(createProfile.error)}</Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={
                createProfile.isPending ||
                (mode === 'AUTOMATIC' &&
                  (providers.isPending || providerOptions.length === 0))
              }
              type="submit"
              variant="contained"
            >
              Save tax settings
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Stack>
  );
}
