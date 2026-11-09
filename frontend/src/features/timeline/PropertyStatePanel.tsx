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
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { formatCurrency, formatDate } from '../../shared/format';
import { localCalendarDate } from '../people/localDate';

type Property = components['schemas']['PropertySummaryRead'];
type PropertyState = components['schemas']['ResolvedPropertyState'];
type Lookup = components['schemas']['LookupRead'];

interface Selection {
  date: string;
  propertyId: string;
}

const displayCode = (value: string) =>
  value
    .toLowerCase()
    .split('_')
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed.';

function amount(value: string | null, currency: string): string {
  return value === null ? 'Not recorded' : formatCurrency(value, currency);
}

export function PropertyStatePanel({ householdId }: { householdId: string }) {
  const [draft, setDraft] = useState<Selection>({
    date: localCalendarDate(),
    propertyId: '',
  });
  const [applied, setApplied] = useState<Selection | null>(null);
  const [validation, setValidation] = useState('');
  const properties = useQuery({
    queryFn: () =>
      apiRequest<Property[]>(
        `/api/v1/households/${householdId}/property-summaries`,
      ),
    queryKey: ['property-summaries', householdId],
    retry: false,
  });
  const statuses = useQuery({
    queryFn: () =>
      apiRequest<Lookup[]>('/api/v1/lookups/property_status?active_only=false'),
    queryKey: ['lookups', 'property_status', 'all'],
    retry: false,
  });
  const state = useQuery({
    enabled: applied !== null,
    queryFn: () =>
      apiRequest<PropertyState>(
        `/api/v1/properties/${applied?.propertyId ?? ''}/state?as_of=${applied?.date ?? ''}`,
      ),
    queryKey: ['property-state', applied?.propertyId, applied?.date],
    retry: false,
  });
  const appliedProperty = properties.data?.find(
    (item) => item.id === applied?.propertyId,
  );
  const dirty =
    applied !== null &&
    (draft.propertyId !== applied.propertyId || draft.date !== applied.date);
  const resolve = () => {
    setValidation('');
    if (!draft.propertyId)
      return setValidation('Choose a property to resolve its position.');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date))
      return setValidation('Choose a valid position date.');
    if (
      applied?.propertyId === draft.propertyId &&
      applied.date === draft.date
    ) {
      void state.refetch();
    } else {
      setApplied({ ...draft });
    }
  };
  const statusName = state.data
    ? statuses.data?.find((item) => item.id === state.data.status_id)
        ?.display_name
    : null;

  return (
    <Stack component="section" spacing={2}>
      <Stack spacing={0.5}>
        <Typography variant="h2">Property position at a date</Typography>
        <Typography color="text.secondary">
          Resolve the recorded value, debt and status using the household
          timeline. Calculations remain backend-authoritative.
        </Typography>
      </Stack>

      {properties.isPending ? (
        <CircularProgress aria-label="Loading properties" size={24} />
      ) : properties.error ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void properties.refetch()}>
              Retry
            </Button>
          }
          severity="error"
        >
          Properties could not be loaded. {errorMessage(properties.error)}
        </Alert>
      ) : properties.data.length === 0 ? (
        <Alert severity="info">
          Add a property before resolving a dated position.
        </Alert>
      ) : (
        <Stack
          direction={{ md: 'row', xs: 'column' }}
          spacing={2}
          sx={{ alignItems: 'flex-start' }}
        >
          <TextField
            label="Property"
            onChange={(input) =>
              setDraft((current) => ({
                ...current,
                propertyId: input.target.value,
              }))
            }
            select
            sx={{ minWidth: 260 }}
            value={draft.propertyId}
          >
            {properties.data.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Position date"
            onChange={(input) =>
              setDraft((current) => ({
                ...current,
                date: input.target.value,
              }))
            }
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={draft.date}
          />
          <Button onClick={resolve} variant="outlined">
            Resolve position
          </Button>
        </Stack>
      )}

      {validation ? <Alert severity="error">{validation}</Alert> : null}
      {dirty ? (
        <Alert severity="info">
          The property or date has changed. Resolve the position to display
          results for the new selection.
        </Alert>
      ) : state.isPending && applied ? (
        <CircularProgress aria-label="Resolving property position" />
      ) : state.error && applied ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void state.refetch()}>
              Retry
            </Button>
          }
          severity="error"
        >
          Property position could not be resolved. {errorMessage(state.error)}
        </Alert>
      ) : state.data && appliedProperty ? (
        <Stack spacing={2}>
          <Alert severity="success">
            Results as of {formatDate(state.data.as_of)} ·{' '}
            {displayCode(state.data.temporal_position)}
          </Alert>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <Paper sx={{ flex: 1, p: 2 }} variant="outlined">
              <Typography color="text.secondary" variant="caption">
                Property value
              </Typography>
              <Typography variant="h6">
                {amount(state.data.property_value, appliedProperty.currency)}
              </Typography>
            </Paper>
            <Paper sx={{ flex: 1, p: 2 }} variant="outlined">
              <Typography color="text.secondary" variant="caption">
                Recorded property debt
              </Typography>
              <Typography variant="h6">
                {amount(
                  state.data.loan_balance_total,
                  appliedProperty.currency,
                )}
              </Typography>
            </Paper>
          </Stack>
          <Typography>
            Status:{' '}
            {statuses.isPending
              ? 'Loading…'
              : statuses.error
                ? 'Reference data unavailable'
                : (statusName ?? 'Unavailable')}{' '}
            · Active asset:{' '}
            {state.data.is_active_asset === null
              ? 'Unknown'
              : state.data.is_active_asset
                ? 'Yes'
                : 'No'}
          </Typography>
          {statuses.error ? (
            <Alert
              action={
                <Button color="inherit" onClick={() => void statuses.refetch()}>
                  Retry status
                </Button>
              }
              severity="warning"
            >
              Property status reference data could not be loaded.
            </Alert>
          ) : null}
          <Typography color="text.secondary" variant="body2">
            Baseline:{' '}
            {state.data.baseline_date
              ? formatDate(state.data.baseline_date)
              : 'None'}{' '}
            · Valuation:{' '}
            {state.data.valuation_date
              ? formatDate(state.data.valuation_date)
              : 'None'}
            {state.data.valuation_date
              ? ` · ${state.data.valuation_type ? displayCode(state.data.valuation_type) : 'Type unavailable'} · ${state.data.valuation_is_estimate === null ? 'Estimate status unavailable' : state.data.valuation_is_estimate ? 'Estimate' : 'Not an estimate'}`
              : ''}{' '}
            · Applied timeline events: {state.data.applied_event_ids.length}
          </Typography>
          {state.data.data_quality_flags.length ? (
            <Alert severity="warning">
              {state.data.data_quality_flags.map(displayCode).join('; ')}
            </Alert>
          ) : null}
        </Stack>
      ) : null}
    </Stack>
  );
}
