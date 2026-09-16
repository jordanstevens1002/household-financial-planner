import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import {
  eventDisplayName,
  LOAN_EVENT_CODES,
  type LoanEventDraft,
  validateLoanEvent,
  valueKind,
  utcInstant,
} from './loanEventValidation';

type Loan = components['schemas']['LoanRead'];
type EventType = components['schemas']['EventTypeRead'];
type FinancialEvent = components['schemas']['FinancialEventRead'];
type Timeline = components['schemas']['TimelineRead'];

const defaults = (): LoanEventDraft => ({
  amount: '',
  classification: 'OBSERVED',
  effectiveAt: new Date().toISOString().slice(0, 16),
  eventTypeId: '',
  idempotencyKey: '',
  notes: '',
  percentage: '',
  termMonths: '',
});

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function LoanEventsPanel({
  canEdit,
  householdId,
  loans,
}: {
  canEdit: boolean;
  householdId: string;
  loans: Loan[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [open, setOpen] = useState(false);
  const [loanId, setLoanId] = useState(loans[0]?.id ?? '');
  const [draft, setDraft] = useState<LoanEventDraft>(defaults);
  const [validationError, setValidationError] = useState('');
  const selectedLoan = loans.find((loan) => loan.id === loanId) ?? loans[0];
  const selectedLoanId = selectedLoan?.id ?? '';
  const eventTypes = useQuery({
    enabled: open,
    queryFn: () => apiRequest<EventType[]>('/api/v1/event-types'),
    queryKey: ['event-types'],
    retry: false,
    select: (items) =>
      items.filter((item) =>
        LOAN_EVENT_CODES.includes(
          item.code as (typeof LOAN_EVENT_CODES)[number],
        ),
      ),
  });
  const timeline = useQuery({
    enabled: open,
    queryFn: () =>
      apiRequest<Timeline>(
        `/api/v1/households/${householdId}/timeline?include_disabled=true`,
      ),
    queryKey: ['household-timeline', householdId, 'include-disabled'],
    retry: false,
  });
  const events = useMemo(
    () =>
      (timeline.data?.events ?? []).filter(
        (event) => event.loan_id === selectedLoanId,
      ),
    [selectedLoanId, timeline.data],
  );
  const selectedType = eventTypes.data?.find(
    (item) => item.id === draft.eventTypeId,
  );
  const kind = valueKind(selectedType?.code ?? '');
  const reset = () => {
    setDraft(defaults());
    setValidationError('');
  };
  const save = useMutation({
    mutationFn: () =>
      apiRequest<FinancialEvent>(`/api/v1/loans/${selectedLoanId}/events`, {
        body: JSON.stringify({
          amount: kind === 'amount' ? draft.amount : null,
          classification: draft.classification,
          effective_at: utcInstant(draft.effectiveAt),
          event_type_id: draft.eventTypeId,
          idempotency_key: draft.idempotencyKey.trim() || null,
          is_enabled: true,
          notes: draft.notes.trim() || null,
          payload:
            kind === 'term' ? { term_months: Number(draft.termMonths) } : {},
          percentage: kind === 'percentage' ? draft.percentage : null,
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onError: (error) => notify(errorMessage(error), 'error'),
    onSuccess: async () => {
      reset();
      notify('Loan event added', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-timeline', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['property-state'] }),
        queryClient.invalidateQueries({
          queryKey: ['loan-schedule', selectedLoanId],
        }),
      ]);
    },
  });
  const submit = () => {
    const error = validateLoanEvent(draft, selectedType?.code ?? '');
    setValidationError(error ?? '');
    if (!error) save.mutate();
  };
  const describeChange = (event: FinancialEvent) => {
    if (event.amount != null)
      return selectedLoan
        ? formatCurrency(event.amount, selectedLoan.currency)
        : event.amount;
    if (event.percentage != null) return `${event.percentage}%`;
    const term = event.payload?.term_months;
    return typeof term === 'number' ? `${term} months` : 'Status change';
  };
  const columns: DataColumn<FinancialEvent>[] = [
    {
      key: 'date',
      label: 'Effective date',
      render: (event) => formatDate(event.effective_at),
    },
    {
      key: 'type',
      label: 'Change',
      render: (event) => eventDisplayName(event.event_type_code),
    },
    { key: 'value', label: 'New value', render: describeChange },
    {
      key: 'classification',
      label: 'Source',
      render: (event) => event.classification,
    },
    {
      key: 'status',
      label: 'Status',
      render: (event) => (event.is_enabled ? 'Enabled' : 'Disabled'),
    },
    {
      key: 'quality',
      label: 'Quality',
      render: (event) =>
        event.data_quality_flags.length ? (
          <Tooltip title={event.data_quality_flags.join(', ')}>
            <IconButton
              aria-label={`Data quality: ${event.data_quality_flags.join(', ')}`}
              size="small"
            >
              <Typography aria-hidden="true" component="span">
                ⓘ
              </Typography>
            </IconButton>
          </Tooltip>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="outlined">
        Loan events
      </Button>
      <Dialog
        fullWidth
        maxWidth="md"
        onClose={() => !save.isPending && setOpen(false)}
        open={open}
      >
        <DialogTitle>Loan events</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              Observed events record changes that happened. Planned events
              describe changes you are considering.
            </Alert>
            <TextField
              label="Loan"
              onChange={(event) => {
                setLoanId(event.target.value);
                reset();
              }}
              select
              value={selectedLoanId}
            >
              {loans.map((loan) => (
                <MenuItem key={loan.id} value={loan.id}>
                  {loan.display_name}
                </MenuItem>
              ))}
            </TextField>
            {timeline.isPending || eventTypes.isPending ? (
              <CircularProgress aria-label="Loading loan events" size={24} />
            ) : timeline.error || eventTypes.error ? (
              <Alert
                action={
                  <Button
                    onClick={() => {
                      void timeline.refetch();
                      void eventTypes.refetch();
                    }}
                  >
                    Retry
                  </Button>
                }
                severity="error"
              >
                Loan events could not be loaded.{' '}
                {errorMessage(timeline.error ?? eventTypes.error)}
              </Alert>
            ) : events.length ? (
              <DataTable
                caption="Loan event history"
                columns={columns}
                getRowKey={(event) => event.id}
                rows={events}
              />
            ) : (
              <EmptyState
                description="Record a change when this loan's rate, repayment, balance or terms change."
                title="No loan events"
              />
            )}
            {canEdit ? (
              <Stack spacing={2}>
                <Typography variant="h3">Add loan event</Typography>
                <Stack direction="row" spacing={2}>
                  <TextField
                    fullWidth
                    label="Change type"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        eventTypeId: event.target.value,
                      }))
                    }
                    select
                    value={draft.eventTypeId}
                  >
                    {(eventTypes.data ?? []).map((item) => (
                      <MenuItem key={item.id} value={item.id}>
                        {eventDisplayName(item.code)}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    fullWidth
                    label="Classification"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        classification: event.target
                          .value as LoanEventDraft['classification'],
                      }))
                    }
                    select
                    value={draft.classification}
                  >
                    <MenuItem value="OBSERVED">Observed — happened</MenuItem>
                    <MenuItem value="PLANNED">Planned — considering</MenuItem>
                  </TextField>
                  <TextField
                    fullWidth
                    helperText="Stored and applied as a UTC instant."
                    label="Effective at (UTC)"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        effectiveAt: event.target.value,
                      }))
                    }
                    slotProps={{ inputLabel: { shrink: true } }}
                    type="datetime-local"
                    value={draft.effectiveAt}
                  />
                </Stack>
                {kind === 'amount' ? (
                  <TextField
                    label={`Amount (${selectedLoan?.currency ?? ''})`}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        amount: event.target.value,
                      }))
                    }
                    value={draft.amount}
                  />
                ) : null}
                {kind === 'percentage' ? (
                  <TextField
                    label="Annual interest rate %"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        percentage: event.target.value,
                      }))
                    }
                    value={draft.percentage}
                  />
                ) : null}
                {kind === 'term' ? (
                  <TextField
                    label="Remaining term (months)"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        termMonths: event.target.value,
                      }))
                    }
                    value={draft.termMonths}
                  />
                ) : null}
                <TextField
                  helperText={`${draft.notes.length.toLocaleString()} / 2,000 characters`}
                  label="Notes (optional)"
                  multiline
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  slotProps={{ htmlInput: { maxLength: 2_000 } }}
                  value={draft.notes}
                />
                <AdvancedSection description="Set an idempotency key only when coordinating retries with another client.">
                  <TextField
                    helperText="Use a stable unique value when retrying an API operation."
                    label="Idempotency key (optional)"
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        idempotencyKey: event.target.value,
                      }))
                    }
                    slotProps={{ htmlInput: { maxLength: 100 } }}
                    value={draft.idempotencyKey}
                  />
                </AdvancedSection>
                {validationError ? (
                  <Alert severity="error">{validationError}</Alert>
                ) : null}
              </Stack>
            ) : (
              <Alert severity="info">
                Only a household editor can add loan events.
              </Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={save.isPending} onClick={() => setOpen(false)}>
            Close
          </Button>
          {canEdit ? (
            <Button
              disabled={
                save.isPending ||
                timeline.isPending ||
                eventTypes.isPending ||
                Boolean(timeline.error || eventTypes.error)
              }
              onClick={submit}
              variant="contained"
            >
              Save event
            </Button>
          ) : null}
        </DialogActions>
      </Dialog>
    </>
  );
}
