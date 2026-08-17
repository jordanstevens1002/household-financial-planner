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
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Ownership = components['schemas']['OwnershipRead'];
type OwnershipPosition = components['schemas']['OwnershipPosition'];
type OwnershipResult = components['schemas']['OwnershipResult'];
type OwnerType = components['schemas']['OwnerType'];
type Person = components['schemas']['PersonRead'];

const schema = z
  .object({
    effectiveFrom: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a start date'),
    effectiveTo: z.string(),
    externalName: z.string().trim().max(200),
    notes: z.string().trim().max(2000),
    ownerType: z.enum([
      'PERSON',
      'HOUSEHOLD',
      'COMPANY',
      'TRUST',
      'RETIREMENT_FUND',
      'EXTERNAL_PARTY',
      'OTHER',
    ]),
    percentage: z
      .string()
      .min(1, 'Enter an ownership percentage')
      .refine(
        (value) =>
          Number.isFinite(Number(value)) &&
          Number(value) > 0 &&
          Number(value) <= 100,
        'Enter a percentage above 0 and no more than 100',
      ),
    personId: z.string(),
  })
  .superRefine((fields, context) => {
    if (fields.effectiveTo && fields.effectiveTo < fields.effectiveFrom) {
      context.addIssue({
        code: 'custom',
        message: 'End date cannot be before the start date',
        path: ['effectiveTo'],
      });
    }
    if (fields.ownerType === 'PERSON' && !fields.personId) {
      context.addIssue({
        code: 'custom',
        message: 'Choose a person',
        path: ['personId'],
      });
    }
    if (
      !['PERSON', 'HOUSEHOLD'].includes(fields.ownerType) &&
      !fields.externalName
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Enter the owner name',
        path: ['externalName'],
      });
    }
  });

type Fields = z.infer<typeof schema>;

const ownerTypes: Array<[OwnerType, string]> = [
  ['HOUSEHOLD', 'Household jointly'],
  ['PERSON', 'A person in this household'],
  ['EXTERNAL_PARTY', 'Someone else'],
];

const advancedOwnerTypes: Array<[OwnerType, string]> = [
  ['COMPANY', 'Company'],
  ['TRUST', 'Trust'],
  ['RETIREMENT_FUND', 'Retirement fund'],
  ['OTHER', 'Other arrangement'],
];

function defaults(): Fields {
  return {
    effectiveFrom: localCalendarDate(),
    effectiveTo: '',
    externalName: '',
    notes: '',
    ownerType: 'HOUSEHOLD',
    percentage: '',
    personId: '',
  };
}

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function ownerName(record: Ownership, people: Person[] | undefined) {
  if (record.owner_type === 'HOUSEHOLD') return 'Household jointly';
  if (record.owner_type === 'PERSON') {
    return (
      people?.find((person) => person.id === record.person_id)?.display_name ??
      'Unknown person'
    );
  }
  return (
    record.external_owner_name ??
    record.owner_type.replaceAll('_', ' ').toLowerCase()
  );
}

export function OwnershipPanel({
  canEdit,
  householdId,
  propertyId,
}: {
  canEdit: boolean;
  householdId: string;
  propertyId: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [asOf, setAsOf] = useState(localCalendarDate());
  const [draftDate, setDraftDate] = useState(asOf);
  const form = useForm<Fields>({
    defaultValues: defaults(),
    resolver: zodResolver(schema),
  });
  const ownerType = useWatch({ control: form.control, name: 'ownerType' });
  const history = useQuery({
    queryFn: () =>
      apiRequest<Ownership[]>(`/api/v1/properties/${propertyId}/ownership`),
    queryKey: ['property-ownership', propertyId],
    retry: false,
  });
  const position = useQuery({
    queryFn: () =>
      apiRequest<OwnershipPosition>(
        `/api/v1/properties/${propertyId}/ownership-position?as_of=${asOf}`,
      ),
    queryKey: ['property-ownership-position', propertyId, asOf],
    retry: false,
  });
  const people = useQuery({
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const create = useMutation<OwnershipResult, Error, Fields>({
    mutationFn: (fields) =>
      apiRequest<OwnershipResult>(
        `/api/v1/properties/${propertyId}/ownership`,
        {
          body: JSON.stringify({
            effective_from: fields.effectiveFrom,
            effective_to: fields.effectiveTo || null,
            external_owner_name: ['PERSON', 'HOUSEHOLD'].includes(
              fields.ownerType,
            )
              ? null
              : fields.externalName,
            notes: fields.notes || null,
            owner_type: fields.ownerType,
            ownership_percentage: fields.percentage,
            person_id: fields.ownerType === 'PERSON' ? fields.personId : null,
          }),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      ),
    onSuccess: async (result) => {
      form.reset(defaults());
      setDialogOpen(false);
      notify(
        result.warnings.length
          ? `Ownership saved. ${result.warnings.join(' ')}`
          : 'Ownership saved',
        result.warnings.length ? 'warning' : 'success',
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['property-ownership', propertyId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['property-ownership-position', propertyId],
        }),
      ]);
    },
  });
  const columns: DataColumn<Ownership>[] = [
    {
      key: 'owner',
      label: 'Owner',
      render: (row) => ownerName(row, people.data),
    },
    {
      key: 'share',
      label: 'Share',
      render: (row) => `${row.ownership_percentage}%`,
    },
    {
      key: 'from',
      label: 'From',
      render: (row) => formatDate(row.effective_from),
    },
    {
      key: 'to',
      label: 'To',
      render: (row) =>
        row.effective_to ? formatDate(row.effective_to) : 'Ongoing',
    },
  ];

  return (
    <Stack spacing={2}>
      <Stack
        direction="row"
        sx={{ alignItems: 'center', justifyContent: 'space-between' }}
      >
        <Typography variant="h2">Ownership</Typography>
        {canEdit ? (
          <Button onClick={() => setDialogOpen(true)} variant="outlined">
            Add ownership record
          </Button>
        ) : null}
      </Stack>
      <Stack direction="row" spacing={2} sx={{ alignItems: 'flex-start' }}>
        <TextField
          label="Ownership date"
          onChange={(event) => setDraftDate(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          type="date"
          value={draftDate}
        />
        <Button
          onClick={() =>
            draftDate === asOf ? void position.refetch() : setAsOf(draftDate)
          }
          variant="outlined"
        >
          Refresh ownership
        </Button>
      </Stack>
      {position.isPending ? (
        <CircularProgress aria-label="Loading ownership position" size={24} />
      ) : position.error ? (
        <Alert
          action={
            <Button onClick={() => void position.refetch()}>Retry</Button>
          }
          severity="error"
        >
          Ownership position could not be loaded. {message(position.error)}
        </Alert>
      ) : position.data ? (
        <Alert severity={position.data.warnings.length ? 'warning' : 'success'}>
          Ownership recorded for {formatDate(position.data.as_of)} totals{' '}
          {position.data.total_percentage}%.
          {position.data.warnings.length
            ? ` ${position.data.warnings.join(' ')}`
            : ''}
        </Alert>
      ) : null}
      {history.isPending ? (
        <CircularProgress aria-label="Loading ownership history" size={24} />
      ) : history.error ? (
        <Alert
          action={<Button onClick={() => void history.refetch()}>Retry</Button>}
          severity="error"
        >
          Ownership history could not be loaded. {message(history.error)}
        </Alert>
      ) : history.data?.length ? (
        <DataTable
          caption="Property ownership history"
          columns={columns}
          getRowKey={(row) => row.id}
          rows={history.data}
        />
      ) : (
        <Alert severity="info">No ownership records have been added yet.</Alert>
      )}
      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={() => setDialogOpen(false)}
        open={dialogOpen}
      >
        <Stack
          component="form"
          onSubmit={(event) =>
            void form.handleSubmit((fields) => create.mutate(fields))(event)
          }
        >
          <DialogTitle>Add ownership record</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField label="Owner" select {...form.register('ownerType')}>
                {ownerTypes.map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label}
                  </MenuItem>
                ))}
                {advancedOwnerTypes.map(([value, label]) => (
                  <MenuItem key={value} value={value}>
                    {label} (advanced)
                  </MenuItem>
                ))}
              </TextField>
              <Alert severity="info">
                <strong>Household jointly</strong> records one combined share
                without assigning it to a particular person.{' '}
                <strong>A person in this household</strong> assigns the share to
                a named household person. <strong>Someone else</strong> is an
                individual outside this household; companies, trusts and other
                legal arrangements are available as advanced owner types.
              </Alert>
              {ownerType === 'PERSON' ? (
                people.error ? (
                  <Alert severity="error">
                    People could not be loaded. {message(people.error)}
                  </Alert>
                ) : (
                  <TextField
                    error={Boolean(form.formState.errors.personId)}
                    helperText={form.formState.errors.personId?.message}
                    label="Person"
                    select
                    {...form.register('personId')}
                  >
                    {(people.data ?? []).map((person) => (
                      <MenuItem key={person.id} value={person.id}>
                        {person.display_name}
                      </MenuItem>
                    ))}
                  </TextField>
                )
              ) : !['HOUSEHOLD'].includes(ownerType) ? (
                <TextField
                  error={Boolean(form.formState.errors.externalName)}
                  helperText={form.formState.errors.externalName?.message}
                  label="Owner name"
                  {...form.register('externalName')}
                />
              ) : null}
              <TextField
                error={Boolean(form.formState.errors.percentage)}
                helperText={form.formState.errors.percentage?.message}
                label="Ownership percentage"
                {...form.register('percentage')}
              />
              <Stack direction="row" spacing={2}>
                <TextField
                  error={Boolean(form.formState.errors.effectiveFrom)}
                  fullWidth
                  helperText={form.formState.errors.effectiveFrom?.message}
                  label="Effective from"
                  slotProps={{ inputLabel: { shrink: true } }}
                  type="date"
                  {...form.register('effectiveFrom')}
                />
                <TextField
                  error={Boolean(form.formState.errors.effectiveTo)}
                  fullWidth
                  helperText={
                    form.formState.errors.effectiveTo?.message ?? 'Optional'
                  }
                  label="Effective to"
                  slotProps={{ inputLabel: { shrink: true } }}
                  type="date"
                  {...form.register('effectiveTo')}
                />
              </Stack>
              <AdvancedSection description="Notes are optional and intended for unusual ownership details.">
                <TextField
                  label="Notes (optional)"
                  multiline
                  rows={3}
                  {...form.register('notes')}
                />
              </AdvancedSection>
              {create.error ? (
                <Alert severity="error">{message(create.error)}</Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button
              disabled={create.isPending}
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={
                create.isPending ||
                (ownerType === 'PERSON' && Boolean(people.error))
              }
              type="submit"
              variant="contained"
            >
              Save ownership
            </Button>
          </DialogActions>
        </Stack>
      </Dialog>
    </Stack>
  );
}
