import {
  Alert,
  Autocomplete,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { useAuth } from '../auth/AuthContext';

type Country = components['schemas']['CountryRead'];
type Currency = components['schemas']['CurrencyRead'];
type TaxProvider = components['schemas']['TaxProviderRead'];
type RetirementProvider = components['schemas']['RetirementProviderRead'];
type PurchaseProvider = components['schemas']['PurchaseProviderRead'];

interface HealthResponse {
  status: string;
  version?: string;
}

interface ProviderRow {
  area: string;
  code: string;
  details: string;
  displayName: string;
}

function requestError(label: string, error: unknown) {
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  const detail = error instanceof Error ? error.message : 'Request failed';
  return `${label}: ${detail}${requestId ? ` (request ${requestId})` : ''}`;
}

export function SettingsPage() {
  const auth = useAuth();
  const live = useQuery({
    queryFn: () => apiRequest<HealthResponse>('/health/live'),
    queryKey: ['health', 'live'],
    retry: false,
  });
  const ready = useQuery({
    queryFn: () => apiRequest<HealthResponse>('/api/v1/system/status'),
    queryKey: ['health', 'ready'],
    retry: false,
  });
  const countries = useQuery({
    queryFn: () => apiRequest<Country[]>('/api/v1/reference/countries'),
    queryKey: ['reference', 'countries'],
  });
  const currencies = useQuery({
    queryFn: () => apiRequest<Currency[]>('/api/v1/reference/currencies'),
    queryKey: ['reference', 'currencies'],
  });
  const taxProviders = useQuery({
    queryFn: () => apiRequest<TaxProvider[]>('/api/v1/tax-providers'),
    queryKey: ['providers', 'tax'],
  });
  const retirementProviders = useQuery({
    queryFn: () =>
      apiRequest<RetirementProvider[]>('/api/v1/retirement-providers'),
    queryKey: ['providers', 'retirement'],
  });
  const purchaseProviders = useQuery({
    queryFn: () => apiRequest<PurchaseProvider[]>('/api/v1/purchase-providers'),
    queryKey: ['providers', 'purchase'],
  });

  const providerRows: ProviderRow[] = [
    ...(taxProviders.data ?? []).map((provider) => ({
      area: 'Tax',
      code: provider.jurisdiction,
      details: provider.supported_tax_years.join(', ') || 'No published years',
      displayName: provider.display_name,
    })),
    ...(retirementProviders.data ?? []).map((provider) => ({
      area: 'Retirement',
      code: provider.code,
      details: 'Installed',
      displayName: provider.display_name,
    })),
    ...(purchaseProviders.data ?? []).map((provider) => ({
      area: 'Purchase planning',
      code: provider.code,
      details: 'Installed',
      displayName: provider.display_name,
    })),
  ];
  const providerColumns: DataColumn<ProviderRow>[] = [
    { key: 'area', label: 'Area', render: (row) => row.area },
    { key: 'name', label: 'Provider', render: (row) => row.displayName },
    { key: 'code', label: 'Code', render: (row) => row.code },
    { key: 'details', label: 'Details', render: (row) => row.details },
  ];
  const errors = [
    live.error && requestError('API health', live.error),
    ready.error && requestError('Database readiness', ready.error),
    countries.error && requestError('Countries', countries.error),
    currencies.error && requestError('Currencies', currencies.error),
    taxProviders.error && requestError('Tax providers', taxProviders.error),
    retirementProviders.error &&
      requestError('Retirement providers', retirementProviders.error),
    purchaseProviders.error &&
      requestError('Purchase providers', purchaseProviders.error),
  ].filter((item): item is string => Boolean(item));
  const loading = [
    live,
    ready,
    countries,
    currencies,
    taxProviders,
    retirementProviders,
    purchaseProviders,
  ].some((query) => query.isLoading);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Settings
        </Typography>
        <Typography color="text.secondary">
          Check this installation, your session and the reference data available
          to planning workflows.
        </Typography>
      </Box>

      {loading ? <CircularProgress aria-label="Loading settings" /> : null}
      {errors.map((error) => (
        <Alert key={error} severity="error">
          {error}
        </Alert>
      ))}

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: '1fr 1fr' }}>
        <Paper sx={{ p: 3 }} variant="outlined">
          <Stack spacing={1.5}>
            <Typography component="h2" variant="h6">
              Connection
            </Typography>
            <Stack direction="row" spacing={1}>
              <Chip
                color={live.data?.status === 'ok' ? 'success' : 'error'}
                label={`API ${live.data?.status === 'ok' ? 'available' : 'unavailable'}`}
              />
              <Chip
                color={ready.data?.status === 'ready' ? 'success' : 'error'}
                label={`Database ${ready.data?.status === 'ready' ? 'ready' : 'unavailable'}`}
              />
            </Stack>
            <Typography>
              Application version:{' '}
              {ready.data?.version ?? live.data?.version ?? 'Unknown'}
            </Typography>
          </Stack>
        </Paper>
        <Paper sx={{ p: 3 }} variant="outlined">
          <Stack spacing={1}>
            <Typography component="h2" variant="h6">
              Current session
            </Typography>
            <Typography>
              Account: {auth.account?.display_name || auth.account?.username}
            </Typography>
            <Typography>Username: {auth.account?.username}</Typography>
            <Typography>Global role: {auth.account?.global_role}</Typography>
            <Chip
              color="success"
              label="Session active"
              sx={{ alignSelf: 'flex-start' }}
            />
          </Stack>
        </Paper>
      </Box>

      <Box>
        <Typography component="h2" variant="h5">
          Installed providers
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Australia is bundled as an example. Additional providers can be
          installed without changing the React application.
        </Typography>
        {providerRows.length ? (
          <DataTable
            caption="Installed financial providers"
            columns={providerColumns}
            getRowKey={(row) => `${row.area}-${row.code}`}
            rows={providerRows}
          />
        ) : loading ? null : (
          <Alert severity="info">No provider metadata is available.</Alert>
        )}
      </Box>

      <AdvancedSection description="Reference catalogues are maintained by the API and are shown here for installation diagnostics.">
        <Stack spacing={2}>
          <Typography>
            {countries.data?.length ?? 0} countries and{' '}
            {currencies.data?.length ?? 0} currencies available
          </Typography>
          <Autocomplete
            options={countries.data ?? []}
            getOptionLabel={(option) => `${option.flag} ${option.display_name}`}
            renderInput={(params) => (
              <TextField {...params} label="Browse countries" />
            )}
          />
          <Autocomplete
            options={currencies.data ?? []}
            getOptionLabel={(option) =>
              `${option.code} — ${option.display_name}`
            }
            renderInput={(params) => (
              <TextField {...params} label="Browse currencies" />
            )}
          />
        </Stack>
      </AdvancedSection>
    </Stack>
  );
}
