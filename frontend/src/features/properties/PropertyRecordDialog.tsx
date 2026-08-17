import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Baseline = components['schemas']['BaselineRead'];
type Lookup = components['schemas']['LookupRead'];
type Valuation = components['schemas']['ValuationRead'];

const money = /^\d+(?:\.\d{1,2})?$/;
const recordSchema = z
  .object({
    accumulatedCostBase: z.string(),
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a record date'),
    debt: z.string(),
    notes: z.string().trim().max(2000),
    recordType: z.enum(['VALUATION', 'BASELINE']),
    source: z.string().trim().max(200),
    statusId: z.string(),
    valuationType: z.enum([
      'USER_ESTIMATE',
      'FORMAL_VALUATION',
      'AGENT_APPRAISAL',
      'AUTOMATED_ESTIMATE',
    ]),
    value: z.string().regex(money, 'Enter a value greater than zero'),
  })
  .superRefine((fields, context) => {
    if (Number(fields.value) <= 0) {
      context.addIssue({
        code: 'custom',
        message: 'Enter a value greater than zero',
        path: ['value'],
      });
    }
    if (fields.recordType === 'BASELINE') {
      if (!money.test(fields.debt) || Number(fields.debt) < 0) {
        context.addIssue({
          code: 'custom',
          message: 'Enter total debt, using 0 when there is none',
          path: ['debt'],
        });
      }
      if (!fields.statusId) {
        context.addIssue({
          code: 'custom',
          message: 'Choose the property use',
          path: ['statusId'],
        });
      }
      if (
        fields.accumulatedCostBase &&
        (!money.test(fields.accumulatedCostBase) ||
          Number(fields.accumulatedCostBase) < 0)
      ) {
        context.addIssue({
          code: 'custom',
          message: 'Enter a non-negative amount',
          path: ['accumulatedCostBase'],
        });
      }
    }
  });

type RecordFields = z.infer<typeof recordSchema>;

const valuationTypes: Array<[RecordFields['valuationType'], string]> = [
  ['USER_ESTIMATE', 'Your estimate'],
  ['FORMAL_VALUATION', 'Formal valuation'],
  ['AGENT_APPRAISAL', 'Agent appraisal'],
  ['AUTOMATED_ESTIMATE', 'Automated estimate'],
];

function valuationTypeIsEstimate(valuationType: RecordFields['valuationType']) {
  return valuationType !== 'FORMAL_VALUATION';
}

function defaults(): RecordFields {
  return {
    accumulatedCostBase: '',
    date: localCalendarDate(),
    debt: '',
    notes: '',
    recordType: 'VALUATION',
    source: '',
    statusId: '',
    valuationType: 'USER_ESTIMATE',
    value: '',
  };
}

function optional(value: string) {
  return value || null;
}

export function PropertyRecordDialog({
  currency,
  householdId,
  onClose,
  open,
  propertyId,
  statuses,
}: {
  currency: string;
  householdId: string;
  onClose: () => void;
  open: boolean;
  propertyId: string;
  statuses: Lookup[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const form = useForm<RecordFields>({
    defaultValues: defaults(),
    resolver: zodResolver(recordSchema),
  });
  const recordType = useWatch({ control: form.control, name: 'recordType' });
  const valuationType = useWatch({
    control: form.control,
    name: 'valuationType',
  });
  const saveRecord = useMutation<Valuation | Baseline, Error, RecordFields>({
    mutationFn: (fields: RecordFields) =>
      fields.recordType === 'VALUATION'
        ? apiRequest<Valuation>(`/api/v1/properties/${propertyId}/valuations`, {
            body: JSON.stringify({
              is_estimate: valuationTypeIsEstimate(fields.valuationType),
              notes: optional(fields.notes),
              source: optional(fields.source),
              valuation_date: fields.date,
              valuation_type: fields.valuationType,
              value: fields.value,
            }),
            csrfToken: auth.csrfToken(),
            method: 'POST',
          })
        : apiRequest<Baseline>(`/api/v1/properties/${propertyId}/baselines`, {
            body: JSON.stringify({
              accumulated_cost_base: optional(fields.accumulatedCostBase),
              baseline_date: fields.date,
              loan_balance_total: fields.debt,
              notes: optional(fields.notes),
              property_value: fields.value,
              status_id: fields.statusId,
            }),
            csrfToken: auth.csrfToken(),
            method: 'POST',
          }),
    onSuccess: async (_, fields) => {
      form.reset(defaults());
      onClose();
      notify(
        fields.recordType === 'VALUATION'
          ? 'Valuation recorded'
          : 'Baseline recorded',
        'success',
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['property-summaries', householdId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['property-state', propertyId],
        }),
      ]);
    },
  });
  const close = () => {
    if (saveRecord.isPending) return;
    form.reset(defaults());
    onClose();
  };

  return (
    <Dialog fullWidth maxWidth="sm" onClose={close} open={open}>
      <Box
        component="form"
        noValidate
        onSubmit={(event) => {
          void form.handleSubmit((fields) => saveRecord.mutate(fields))(event);
        }}
      >
        <DialogTitle>Add a dated property record</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Record type"
              select
              {...form.register('recordType')}
            >
              <MenuItem value="VALUATION">Valuation</MenuItem>
              <MenuItem value="BASELINE">Complete position baseline</MenuItem>
            </TextField>
            <Alert severity="info">
              {recordType === 'VALUATION'
                ? 'A valuation updates property value only. It does not change debt or property use.'
                : 'A baseline records value, total debt and property use together when detailed history is unavailable.'}
            </Alert>
            <Stack direction="row" spacing={2}>
              <TextField
                error={Boolean(form.formState.errors.date)}
                fullWidth
                helperText={form.formState.errors.date?.message}
                label="Record date"
                slotProps={{ inputLabel: { shrink: true } }}
                type="date"
                {...form.register('date')}
              />
              <TextField
                error={Boolean(form.formState.errors.value)}
                fullWidth
                helperText={form.formState.errors.value?.message}
                label={`Property value (${currency})`}
                {...form.register('value')}
              />
            </Stack>
            {recordType === 'VALUATION' ? (
              <>
                <TextField
                  label="Valuation type"
                  select
                  {...form.register('valuationType')}
                >
                  {valuationTypes.map(([value, label]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
                <Alert severity="info">
                  {valuationTypeIsEstimate(valuationType)
                    ? 'This valuation type is recorded as an estimate.'
                    : 'A formal valuation is recorded as a non-estimate.'}
                </Alert>
              </>
            ) : (
              <>
                <TextField
                  error={Boolean(form.formState.errors.debt)}
                  helperText={
                    form.formState.errors.debt?.message ??
                    'Enter 0 when there is no debt'
                  }
                  label={`Total property debt (${currency})`}
                  {...form.register('debt')}
                />
                <TextField
                  error={Boolean(form.formState.errors.statusId)}
                  helperText={form.formState.errors.statusId?.message}
                  label="Property use"
                  select
                  {...form.register('statusId')}
                >
                  {statuses.map((status) => (
                    <MenuItem key={status.id} value={status.id}>
                      {status.display_name}
                    </MenuItem>
                  ))}
                </TextField>
              </>
            )}
            <AdvancedSection description="Record optional source, cost-base and household notes.">
              <Stack spacing={2}>
                {recordType === 'VALUATION' ? (
                  <TextField
                    label="Source (optional)"
                    {...form.register('source')}
                  />
                ) : (
                  <TextField
                    error={Boolean(form.formState.errors.accumulatedCostBase)}
                    helperText={
                      form.formState.errors.accumulatedCostBase?.message
                    }
                    label={`Accumulated cost base (${currency}, optional)`}
                    {...form.register('accumulatedCostBase')}
                  />
                )}
                <TextField
                  label="Notes (optional)"
                  minRows={2}
                  multiline
                  {...form.register('notes')}
                />
              </Stack>
            </AdvancedSection>
            {saveRecord.error ? (
              <Alert severity="error">
                Property record could not be saved.{' '}
                {saveRecord.error instanceof Error
                  ? saveRecord.error.message
                  : 'The request failed'}
              </Alert>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>Cancel</Button>
          <Button
            disabled={saveRecord.isPending}
            type="submit"
            variant="contained"
          >
            Save record
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
