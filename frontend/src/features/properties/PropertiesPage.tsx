import {
  Alert,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { loadSelection, saveSelection } from '../../app/selectionStorage';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useHousehold } from '../households/HouseholdContext';
import { localCalendarDate } from '../people/localDate';
import { PropertyCreateDialog } from './PropertyCreateDialog';

type Lookup = components['schemas']['LookupRead'];
type Property = components['schemas']['PropertyRead'];
type PropertySummary = components['schemas']['PropertySummaryRead'];
type PropertyState = components['schemas']['ResolvedPropertyState'];
type HouseholdAccess = components['schemas']['HouseholdAccessRead'];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function optionalMoney(value: string | null, currency: string) {
  return value === null ? 'Not recorded' : formatCurrency(value, currency);
}

function optionalDate(value: string | null | undefined) {
  return value == null ? 'Not recorded' : formatDate(value);
}

function PositionAmount({
  currency,
  description,
  label,
  value,
}: {
  currency: string;
  description?: string;
  label: string;
  value: string | null;
}) {
  return (
    <Paper sx={{ flex: '1 1 200px', p: 2 }} variant="outlined">
      <Typography color="text.secondary" variant="body2">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }} variant="h6">
        {optionalMoney(value, currency)}
      </Typography>
      {description ? (
        <Typography color="text.secondary" variant="body2">
          {description}
        </Typography>
      ) : null}
    </Paper>
  );
}

export function PropertiesPage() {
  const household = useHousehold();
  const householdId = household.selected?.id ?? null;
  const [selectedId, setSelectedId] = useState(() => loadSelection('property'));
  const [createOpen, setCreateOpen] = useState(false);
  const [asOf, setAsOf] = useState(localCalendarDate());
  const [draftDate, setDraftDate] = useState(asOf);
  const [dateError, setDateError] = useState('');
  const properties = useQuery({
    enabled: householdId !== null,
    queryFn: () =>
      apiRequest<PropertySummary[]>(
        `/api/v1/households/${householdId}/property-summaries`,
      ),
    queryKey: ['property-summaries', householdId],
    retry: false,
  });
  const propertyTypes = useQuery({
    enabled: householdId !== null,
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/property_type'),
    queryKey: ['lookups', 'property_type'],
    retry: false,
  });
  const statuses = useQuery({
    enabled: householdId !== null,
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/property_status'),
    queryKey: ['lookups', 'property_status'],
    retry: false,
  });
  const access = useQuery({
    enabled: householdId !== null,
    queryFn: () =>
      apiRequest<HouseholdAccess>(`/api/v1/households/${householdId}/access`),
    queryKey: ['household-access', householdId],
    retry: false,
  });
  const validSelectedId =
    properties.data?.some((property) => property.id === selectedId) === true
      ? selectedId
      : null;
  const selectedSummary =
    properties.data?.find((property) => property.id === validSelectedId) ??
    null;
  const detail = useQuery({
    enabled: validSelectedId !== null,
    queryFn: () =>
      apiRequest<Property>(`/api/v1/properties/${validSelectedId}`),
    queryKey: ['property', validSelectedId],
    retry: false,
  });
  const state = useQuery({
    enabled: validSelectedId !== null,
    queryFn: () =>
      apiRequest<PropertyState>(
        `/api/v1/properties/${validSelectedId}/state?as_of=${asOf}`,
      ),
    queryKey: ['property-state', validSelectedId, asOf],
    retry: false,
  });

  useEffect(() => {
    if (properties.data && selectedId !== null && validSelectedId === null) {
      saveSelection('property', null);
    }
  }, [properties.data, selectedId, validSelectedId]);

  if (!household.selected) {
    return (
      <Stack spacing={3}>
        <Typography component="h1" variant="h4">
          Properties
        </Typography>
        <EmptyState
          description="Choose a household before reviewing its property position."
          title="No household selected"
        />
        <Button
          component={Link}
          sx={{ alignSelf: 'flex-start' }}
          to="/households"
        >
          Choose a household
        </Button>
      </Stack>
    );
  }

  const lookupName = (
    items: Lookup[] | undefined,
    id: string,
    isPending = false,
    hasError = false,
  ) => {
    if (isPending) return 'Loading…';
    if (hasError) return 'Reference data unavailable';
    return items?.find((item) => item.id === id)?.display_name ?? 'Unavailable';
  };
  const selectProperty = (property: PropertySummary) => {
    setSelectedId(property.id);
    saveSelection('property', property.id);
  };
  const applyDate = () => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(draftDate)) {
      setDateError('Use YYYY-MM-DD');
      return;
    }
    setDateError('');
    if (draftDate === asOf) void state.refetch();
    else setAsOf(draftDate);
  };
  const columns: DataColumn<PropertySummary>[] = [
    { key: 'name', label: 'Property', render: (row) => row.display_name },
    {
      key: 'type',
      label: 'Type',
      render: (row) =>
        lookupName(
          propertyTypes.data,
          row.property_type_id,
          propertyTypes.isPending,
          Boolean(propertyTypes.error),
        ),
    },
    {
      key: 'status',
      label: 'Current use',
      render: (row) =>
        lookupName(
          statuses.data,
          row.current_status_id,
          statuses.isPending,
          Boolean(statuses.error),
        ),
    },
    {
      key: 'purchase',
      label: 'Purchase price',
      render: (row) => optionalMoney(row.purchase_price, row.currency),
    },
    {
      key: 'value',
      label: 'Recorded value',
      render: (row) => optionalMoney(row.current_value, row.currency),
    },
    {
      key: 'debt',
      label: 'Recorded debt',
      render: (row) => optionalMoney(row.total_property_debt, row.currency),
    },
    {
      key: 'position-date',
      label: 'Recorded at',
      render: (row) => optionalDate(row.position_date),
    },
    {
      key: 'action',
      label: 'Details',
      render: (row) => (
        <Button
          onClick={() => selectProperty(row)}
          size="small"
          variant={validSelectedId === row.id ? 'contained' : 'text'}
        >
          {validSelectedId === row.id ? 'Selected' : 'View'}
        </Button>
      ),
    },
  ];

  return (
    <Stack spacing={3}>
      <Stack spacing={1}>
        <Typography component="h1" variant="h4">
          Properties
        </Typography>
        <Typography color="text.secondary">
          Review purchase history, current value and debt as separate parts of
          your household property position.
        </Typography>
      </Stack>
      {access.isPending ? (
        <CircularProgress
          aria-label="Checking property permissions"
          size={24}
        />
      ) : access.error ? (
        <Alert severity="error">
          Property permissions could not be checked.{' '}
          {errorMessage(access.error)}
        </Alert>
      ) : access.data?.can_edit ? (
        <Button
          disabled={
            propertyTypes.isPending ||
            statuses.isPending ||
            Boolean(propertyTypes.error) ||
            Boolean(statuses.error)
          }
          onClick={() => setCreateOpen(true)}
          sx={{ alignSelf: 'flex-start' }}
          variant="contained"
        >
          Add property
        </Button>
      ) : (
        <Alert severity="info">
          You have view-only access to properties in this household.
        </Alert>
      )}
      {properties.isPending ? (
        <CircularProgress aria-label="Loading properties" />
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
      ) : properties.data?.length ? (
        <DataTable
          caption="Household properties"
          columns={columns}
          getRowKey={(row) => row.id}
          rows={properties.data}
        />
      ) : (
        <EmptyState
          description={
            access.data?.can_edit
              ? 'Use Add property to record where things stand now or enter purchase history.'
              : 'No properties have been recorded for this household.'
          }
          title="No properties recorded"
        />
      )}
      {propertyTypes.error ? (
        <Alert
          action={
            <Button
              color="inherit"
              onClick={() => void propertyTypes.refetch()}
            >
              Retry property types
            </Button>
          }
          severity="warning"
        >
          Property types could not be loaded.{' '}
          {errorMessage(propertyTypes.error)}
        </Alert>
      ) : null}
      {statuses.error ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void statuses.refetch()}>
              Retry property uses
            </Button>
          }
          severity="warning"
        >
          Property uses could not be loaded. {errorMessage(statuses.error)}
        </Alert>
      ) : null}
      {selectedSummary ? (
        <Stack spacing={2}>
          <Typography variant="h2">{selectedSummary.display_name}</Typography>
          {detail.isPending ? (
            <CircularProgress aria-label="Loading property details" />
          ) : detail.error ? (
            <Alert severity="error">
              Property details could not be loaded. {errorMessage(detail.error)}
            </Alert>
          ) : detail.data ? (
            <Stack spacing={1}>
              <Typography>
                {[
                  detail.data.address_line_1,
                  detail.data.suburb_or_locality,
                  detail.data.state_or_region,
                  detail.data.postal_code,
                  detail.data.country_code,
                ]
                  .filter(Boolean)
                  .join(', ') || 'Address not recorded'}
              </Typography>
              <Typography color="text.secondary">
                Purchased {optionalDate(detail.data.purchase_date)} · Sold{' '}
                {optionalDate(detail.data.sale_date)}
              </Typography>
              {detail.data.notes ? (
                <Typography>{detail.data.notes}</Typography>
              ) : null}
            </Stack>
          ) : null}
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
            <PositionAmount
              currency={selectedSummary.currency}
              label="Purchase price"
              value={selectedSummary.purchase_price}
            />
            <PositionAmount
              currency={selectedSummary.currency}
              description={`Recorded ${optionalDate(selectedSummary.position_date)}`}
              label="Latest recorded value"
              value={selectedSummary.current_value}
            />
            <PositionAmount
              currency={selectedSummary.currency}
              description={`Recorded ${optionalDate(selectedSummary.position_date)}`}
              label="Latest recorded debt"
              value={selectedSummary.total_property_debt}
            />
          </Stack>
          <Typography variant="h2">Position at a date</Typography>
          <Stack direction="row" spacing={2} sx={{ alignItems: 'flex-start' }}>
            <TextField
              error={Boolean(dateError)}
              helperText={dateError}
              label="Position date"
              onChange={(event) => setDraftDate(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              type="date"
              value={draftDate}
            />
            <Button onClick={applyDate} variant="outlined">
              Refresh position
            </Button>
          </Stack>
          {state.isPending ? (
            <CircularProgress aria-label="Loading property position" />
          ) : state.error ? (
            <Alert severity="error">
              Property position could not be loaded. {errorMessage(state.error)}
            </Alert>
          ) : state.data ? (
            <Stack spacing={2}>
              <Alert severity={draftDate === asOf ? 'success' : 'info'}>
                Results as of {state.data.as_of} (
                {state.data.temporal_position.toLowerCase()}).
                {draftDate === asOf
                  ? ''
                  : ' The position date has changed; refresh to resolve it.'}
              </Alert>
              <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
                <PositionAmount
                  currency={selectedSummary.currency}
                  label="Property value"
                  value={state.data.property_value}
                />
                <PositionAmount
                  currency={selectedSummary.currency}
                  label="Total property debt"
                  value={state.data.loan_balance_total}
                />
              </Stack>
              <Typography>
                Status:{' '}
                {lookupName(
                  statuses.data,
                  state.data.status_id,
                  statuses.isPending,
                  Boolean(statuses.error),
                )}{' '}
                · Active asset:{' '}
                {state.data.is_active_asset === null
                  ? 'Unknown'
                  : state.data.is_active_asset
                    ? 'Yes'
                    : 'No'}
              </Typography>
              {state.data.data_quality_flags.length ? (
                <Alert severity="warning">
                  Data quality: {state.data.data_quality_flags.join(', ')}
                </Alert>
              ) : null}
            </Stack>
          ) : null}
        </Stack>
      ) : properties.data?.length ? (
        <Alert severity="info">
          Choose a property to review its details and dated position.
        </Alert>
      ) : null}
      <PropertyCreateDialog
        currency={household.selected.currency}
        householdId={household.selected.id}
        jurisdiction={household.selected.jurisdiction}
        onClose={() => setCreateOpen(false)}
        onCreated={(propertyId) => {
          setSelectedId(propertyId);
          saveSelection('property', propertyId);
        }}
        open={createOpen}
        properties={properties.data ?? []}
        propertyTypes={propertyTypes.data ?? []}
        statuses={statuses.data ?? []}
      />
    </Stack>
  );
}
