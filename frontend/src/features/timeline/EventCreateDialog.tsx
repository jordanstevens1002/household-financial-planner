import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { utcInstant } from '../properties/loanEventValidation';

type EventType = components['schemas']['EventTypeRead'];
type FinancialEvent = components['schemas']['FinancialEventRead'];
type Classification = components['schemas']['EventClassification'];
type Person = components['schemas']['PersonRead'];
type Property = components['schemas']['PropertySummaryRead'];
type Loan = components['schemas']['LoanRead'];

interface Draft {
  amount: string;
  classification: Classification;
  effectiveAt: string;
  eventTypeId: string;
  idempotencyKey: string;
  loanId: string;
  notes: string;
  payload: string;
  percentage: string;
  personId: string;
  propertyId: string;
}

const blank: Draft = {
  amount: '',
  classification: 'PLANNED',
  effectiveAt: '',
  eventTypeId: '',
  idempotencyKey: '',
  loanId: '',
  notes: '',
  payload: '{}',
  percentage: '',
  personId: '',
  propertyId: '',
};
const money = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const percentage = /^(?:100(?:\.0{1,4})?|\d{1,2}(?:\.\d{1,4})?)$/;
const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed';

export function EventCreateDialog({
  eventTypes,
  householdId,
  onClose,
}: {
  eventTypes: EventType[];
  householdId: string;
  onClose: () => void;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [draft, setDraft] = useState(blank);
  const [validation, setValidation] = useState('');
  const field =
    (key: keyof Draft) => (event: React.ChangeEvent<HTMLInputElement>) =>
      setDraft((current) => ({ ...current, [key]: event.target.value }));
  const people = useQuery({
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const properties = useQuery({
    queryFn: () =>
      apiRequest<Property[]>(`/api/v1/households/${householdId}/properties`),
    queryKey: ['property-summaries', householdId],
    retry: false,
  });
  const loans = useQuery({
    queryFn: () =>
      apiRequest<Loan[]>(`/api/v1/households/${householdId}/loans`),
    queryKey: ['household-loans', householdId],
    retry: false,
  });
  const referencesFailed = people.error || properties.error || loans.error;
  const save = useMutation({
    mutationFn: (body: components['schemas']['FinancialEventCreate']) =>
      apiRequest<FinancialEvent>(`/api/v1/households/${householdId}/events`, {
        body: JSON.stringify(body),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onError: (error) => notification.notify(message(error), 'error'),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({
        queryKey: ['household-timeline', householdId],
      });
      notification.notify(
        created.data_quality_flags.length
          ? 'Event added with data-quality notes.'
          : 'Event added.',
        created.data_quality_flags.length ? 'warning' : 'success',
      );
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    if (!draft.eventTypeId || !draft.effectiveAt)
      return setValidation('Event type and effective time are required.');
    if (draft.amount && !money.test(draft.amount.trim()))
      return setValidation(
        'Amount requires up to 16 whole digits and 2 decimal places.',
      );
    if (draft.percentage && !percentage.test(draft.percentage.trim()))
      return setValidation(
        'Percentage must be from 0 to 100 with up to 4 decimal places.',
      );
    if (draft.notes.length > 2_000 || draft.idempotencyKey.length > 100)
      return setValidation(
        'Notes or idempotency key exceed the permitted length.',
      );
    let payload: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(draft.payload);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
        throw new Error();
      payload = parsed as Record<string, unknown>;
    } catch {
      return setValidation('Advanced payload must be a JSON object.');
    }
    save.mutate({
      amount: draft.amount || null,
      classification: draft.classification,
      effective_at: utcInstant(draft.effectiveAt),
      event_type_id: draft.eventTypeId,
      idempotency_key: draft.idempotencyKey.trim() || null,
      is_enabled: true,
      loan_id: draft.loanId || null,
      notes: draft.notes.trim() || null,
      payload,
      percentage: draft.percentage || null,
      person_id: draft.personId || null,
      property_id: draft.propertyId || null,
    });
  };
  return (
    <Dialog
      fullWidth
      maxWidth="md"
      onClose={save.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Add timeline event</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {referencesFailed ? (
            <Alert severity="warning">
              Some related-record catalogues could not be loaded. Their
              selectors remain disabled, but a household-level event can still
              be added.
            </Alert>
          ) : null}
          <TextField
            label="Event type"
            onChange={field('eventTypeId')}
            select
            value={draft.eventTypeId}
          >
            {eventTypes.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Classification"
            onChange={field('classification')}
            select
            value={draft.classification}
          >
            <MenuItem value="OBSERVED">Observed — happened</MenuItem>
            <MenuItem value="PLANNED">Planned — considering</MenuItem>
            <MenuItem value="PROJECTED">Projected — calculated</MenuItem>
          </TextField>
          <TextField
            label="Effective time (UTC)"
            onChange={field('effectiveAt')}
            slotProps={{ inputLabel: { shrink: true } }}
            type="datetime-local"
            value={draft.effectiveAt}
          />
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Amount (optional)"
              onChange={field('amount')}
              value={draft.amount}
            />
            <TextField
              fullWidth
              label="Percentage (optional)"
              onChange={field('percentage')}
              value={draft.percentage}
            />
          </Stack>
          <TextField
            disabled={properties.isPending || Boolean(properties.error)}
            label="Property (optional)"
            onChange={field('propertyId')}
            select
            value={draft.propertyId}
          >
            <MenuItem value="">None</MenuItem>
            {(properties.data ?? []).map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            disabled={people.isPending || Boolean(people.error)}
            label="Person (optional)"
            onChange={field('personId')}
            select
            value={draft.personId}
          >
            <MenuItem value="">None</MenuItem>
            {(people.data ?? []).map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            disabled={loans.isPending || Boolean(loans.error)}
            label="Loan (optional)"
            onChange={field('loanId')}
            select
            value={draft.loanId}
          >
            <MenuItem value="">None</MenuItem>
            {(loans.data ?? []).map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Notes (optional)"
            multiline
            minRows={2}
            onChange={field('notes')}
            value={draft.notes}
          />
          <AdvancedSection description="Generic payload and idempotency controls are intended for specialist event integrations.">
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                label="Payload (JSON)"
                multiline
                minRows={3}
                onChange={field('payload')}
                value={draft.payload}
              />
              <TextField
                label="Idempotency key (optional)"
                onChange={field('idempotencyKey')}
                value={draft.idempotencyKey}
              />
            </Stack>
          </AdvancedSection>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={save.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={save.isPending} onClick={submit} variant="contained">
          Add event
        </Button>
      </DialogActions>
    </Dialog>
  );
}
