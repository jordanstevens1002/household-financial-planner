import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';

type Event = components['schemas']['FinancialEventRead'];

const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The event could not be updated.';

export function EventCorrectionDialog({
  event,
  householdId,
  onClose,
}: {
  event: Event;
  householdId: string;
  onClose: () => void;
}) {
  const auth = useAuth();
  const notification = useNotification();
  const queryClient = useQueryClient();
  const [effectiveDate, setEffectiveDate] = useState(
    event.effective_at.slice(0, 10),
  );
  const [notes, setNotes] = useState(event.notes ?? '');
  const [validation, setValidation] = useState('');
  const update = useMutation({
    mutationFn: () =>
      apiRequest<Event>(`/api/v1/events/${event.id}`, {
        body: JSON.stringify({
          effective_at: `${effectiveDate}T00:00:00Z`,
          notes: notes.trim() || null,
        }),
        csrfToken: auth.csrfToken(),
        method: 'PATCH',
      }),
    onError: (error) => notification.notify(message(error), 'error'),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-timeline', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['property-state'] }),
        queryClient.invalidateQueries({ queryKey: ['loan-schedule'] }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
      ]);
      notification.notify('Event updated.', 'success');
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    if (!effectiveDate) return setValidation('Effective date is required.');
    if (notes.length > 2_000)
      return setValidation('Notes cannot exceed 2,000 characters.');
    update.mutate();
  };

  return (
    <Dialog
      fullWidth
      maxWidth="sm"
      onClose={update.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Correct timeline event</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="info">
            This changes the planning date and notes. The event type and
            financial details remain unchanged.
          </Alert>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          <TextField
            label="Effective date"
            onChange={(input) => setEffectiveDate(input.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={effectiveDate}
          />
          <TextField
            label="Notes (optional)"
            minRows={3}
            multiline
            onChange={(input) => setNotes(input.target.value)}
            value={notes}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={update.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={update.isPending}
          onClick={submit}
          variant="contained"
        >
          Save correction
        </Button>
      </DialogActions>
    </Dialog>
  );
}
