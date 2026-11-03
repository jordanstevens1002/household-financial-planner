import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  FormControlLabel,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatDate } from '../../shared/format';
import { useHousehold } from '../households/HouseholdContext';

type Event = components['schemas']['FinancialEventRead'];
type Timeline = components['schemas']['TimelineRead'];

interface Filters {
  from: string;
  includeDisabled: boolean;
  to: string;
}

const initialFilters: Filters = { from: '', includeDisabled: false, to: '' };

const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'The timeline request failed';

function displayCode(value: string): string {
  return value
    .toLowerCase()
    .split('_')
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

function relatedRecord(event: Event): string {
  if (event.property_id) return `Property · ${event.property_id}`;
  if (event.loan_id) return `Loan · ${event.loan_id}`;
  if (event.person_id) return `Person · ${event.person_id}`;
  return 'Household';
}

function FlagInfo({ event }: { event: Event }) {
  if (event.data_quality_flags.length === 0) return <Typography>—</Typography>;
  const description = event.data_quality_flags.map(displayCode).join('; ');
  return (
    <Tooltip arrow title={description}>
      <IconButton
        aria-label={`Data-quality notes: ${description}`}
        size="small"
      >
        <span aria-hidden style={{ fontWeight: 700 }}>
          i
        </span>
      </IconButton>
    </Tooltip>
  );
}

const columns: DataColumn<Event>[] = [
  {
    key: 'date',
    label: 'Effective date',
    render: (event) => formatDate(event.effective_at),
  },
  {
    key: 'event',
    label: 'Event',
    render: (event) => (
      <Stack spacing={0.25}>
        <Typography variant="body2">
          {displayCode(event.event_type_code)}
        </Typography>
        {event.notes ? (
          <Typography color="text.secondary" variant="caption">
            {event.notes}
          </Typography>
        ) : null}
      </Stack>
    ),
  },
  {
    key: 'classification',
    label: 'Provenance',
    render: (event) => (
      <Chip
        label={displayCode(event.classification)}
        size="small"
        variant="outlined"
      />
    ),
  },
  { key: 'record', label: 'Related to', render: relatedRecord },
  {
    key: 'status',
    label: 'Status',
    render: (event) => (
      <Chip
        color={event.is_enabled ? 'success' : 'default'}
        label={event.is_enabled ? 'Enabled' : 'Disabled'}
        size="small"
      />
    ),
  },
  {
    key: 'quality',
    label: 'Data quality',
    render: (event) => <FlagInfo event={event} />,
  },
];

export function TimelinePage() {
  const { error: householdError, loading, selected } = useHousehold();
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const invalidRange = Boolean(draft.from && draft.to && draft.from > draft.to);
  const householdId = selected?.id ?? '';
  const timeline = useQuery({
    enabled: Boolean(householdId),
    queryFn: () => {
      const query = new URLSearchParams();
      if (filters.from) query.set('from_date', filters.from);
      if (filters.to) query.set('to_date', filters.to);
      if (filters.includeDisabled) query.set('include_disabled', 'true');
      const suffix = query.size ? `?${query.toString()}` : '';
      return apiRequest<Timeline>(
        `/api/v1/households/${householdId}/timeline${suffix}`,
      );
    },
    queryKey: ['household-timeline', householdId, filters],
  });

  if (loading) return <CircularProgress aria-label="Loading households" />;
  if (householdError)
    return <Alert severity="error">{householdError.message}</Alert>;
  if (!selected)
    return (
      <EmptyState
        description="Choose or create a household before reviewing its financial history."
        title="No household selected"
      />
    );

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Timeline
        </Typography>
        <Typography color="text.secondary">
          Review observed, planned and projected events for{' '}
          {selected.display_name}.
        </Typography>
      </Box>

      <Box
        component="form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!invalidRange) setFilters(draft);
        }}
      >
        <Stack
          direction={{ md: 'row', xs: 'column' }}
          spacing={2}
          sx={{ alignItems: 'flex-start' }}
        >
          <TextField
            error={invalidRange}
            helperText={
              invalidRange ? 'From date must not be after to date.' : 'Optional'
            }
            label="From"
            onChange={(event) =>
              setDraft((current) => ({ ...current, from: event.target.value }))
            }
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={draft.from}
          />
          <TextField
            error={invalidRange}
            helperText="Optional"
            label="To"
            onChange={(event) =>
              setDraft((current) => ({ ...current, to: event.target.value }))
            }
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={draft.to}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={draft.includeDisabled}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    includeDisabled: event.target.checked,
                  }))
                }
              />
            }
            label="Include disabled events"
          />
          <Button disabled={invalidRange} type="submit" variant="contained">
            Refresh timeline
          </Button>
          <Button
            onClick={() => {
              setDraft(initialFilters);
              setFilters(initialFilters);
            }}
          >
            Clear filters
          </Button>
        </Stack>
      </Box>

      {timeline.isPending ? (
        <CircularProgress aria-label="Loading timeline" />
      ) : timeline.error ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void timeline.refetch()}>
              Retry
            </Button>
          }
          severity="error"
        >
          {errorMessage(timeline.error)}
        </Alert>
      ) : timeline.data.events.length === 0 ? (
        <EmptyState
          description={
            filters.from || filters.to || filters.includeDisabled
              ? 'No events match the selected timeline filters.'
              : 'Events will appear here as household activity is recorded.'
          }
          title="No timeline events"
        />
      ) : (
        <>
          {timeline.data.data_quality_flags.length > 0 ? (
            <Alert severity="info">
              Some events have data-quality notes. Use the information buttons
              in the table for details.
            </Alert>
          ) : null}
          <DataTable
            caption="Household timeline"
            columns={columns}
            getRowKey={(event) => event.id}
            rows={timeline.data.events}
          />
        </>
      )}
    </Stack>
  );
}
