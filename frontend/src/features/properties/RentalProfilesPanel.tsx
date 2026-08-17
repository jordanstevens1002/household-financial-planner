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
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type RentalProfile = components['schemas']['RentalProfileRead'];

const optionalNonNegative = (label: string) =>
  z
    .string()
    .refine(
      (value) =>
        value.trim() === '' ||
        (Number.isFinite(Number(value)) && Number(value) >= 0),
      `${label} must be zero or more`,
    );

const percentage = (label: string) =>
  z
    .string()
    .refine(
      (value) =>
        value.trim() !== '' &&
        Number.isFinite(Number(value)) &&
        Number(value) >= 0 &&
        Number(value) <= 100,
      `${label} must be between 0 and 100`,
    );

const schema = z
  .object({
    chargedRent: z
      .string()
      .min(1, 'Enter the rent charged')
      .refine(
        (value) =>
          value.trim() !== '' &&
          Number.isFinite(Number(value)) &&
          Number(value) >= 0,
        'Rent charged must be zero or more',
      ),
    displayName: z.string().trim().min(1, 'Enter a name').max(200),
    effectiveFrom: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a start date'),
    effectiveTo: z.string(),
    frequency: z.enum([
      'WEEKLY',
      'FORTNIGHTLY',
      'MONTHLY',
      'QUARTERLY',
      'ANNUAL',
    ]),
    lettingFee: optionalNonNegative('Letting fee'),
    managementRate: percentage('Management fee'),
    marketRent: optionalNonNegative('Market rent'),
    notes: z.string().trim().max(2000),
    rentalShare: z.string(),
    scope: z.enum(['WHOLE', 'PARTIAL']),
    vacancyRate: percentage('Vacancy rate'),
  })
  .superRefine((fields, context) => {
    if (fields.effectiveTo && fields.effectiveTo < fields.effectiveFrom) {
      context.addIssue({
        code: 'custom',
        message: 'End date cannot be before the start date',
        path: ['effectiveTo'],
      });
    }
    if (
      fields.scope === 'PARTIAL' &&
      (fields.rentalShare.trim() === '' ||
        !Number.isFinite(Number(fields.rentalShare)) ||
        Number(fields.rentalShare) <= 0 ||
        Number(fields.rentalShare) > 100)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Enter a share above 0 and no more than 100',
        path: ['rentalShare'],
      });
    }
  });

type Fields = z.infer<typeof schema>;

const frequencies: Array<[Fields['frequency'], string]> = [
  ['WEEKLY', 'Weekly'],
  ['FORTNIGHTLY', 'Fortnightly'],
  ['MONTHLY', 'Monthly'],
  ['QUARTERLY', 'Quarterly'],
  ['ANNUAL', 'Annual'],
];

function defaults(): Fields {
  return {
    chargedRent: '',
    displayName: '',
    effectiveFrom: localCalendarDate(),
    effectiveTo: '',
    frequency: 'WEEKLY',
    lettingFee: '',
    managementRate: '0',
    marketRent: '',
    notes: '',
    rentalShare: '',
    scope: 'WHOLE',
    vacancyRate: '0',
  };
}

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function RentalProfilesPanel({
  canEdit,
  currency,
  propertyId,
}: {
  canEdit: boolean;
  currency: string;
  propertyId: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [dialogOpen, setDialogOpen] = useState(false);
  const form = useForm<Fields>({
    defaultValues: defaults(),
    resolver: zodResolver(schema),
  });
  const scope = useWatch({ control: form.control, name: 'scope' });
  const profiles = useQuery({
    queryFn: () =>
      apiRequest<RentalProfile[]>(
        `/api/v1/properties/${propertyId}/rental-profiles`,
      ),
    queryKey: ['property-rental-profiles', propertyId],
    retry: false,
  });
  const create = useMutation<RentalProfile, Error, Fields>({
    mutationFn: (fields) =>
      apiRequest<RentalProfile>(
        `/api/v1/properties/${propertyId}/rental-profiles`,
        {
          body: JSON.stringify({
            charged_rent_amount: fields.chargedRent,
            display_name: fields.displayName,
            effective_from: fields.effectiveFrom,
            effective_to: fields.effectiveTo || null,
            frequency: fields.frequency,
            letting_fee: fields.lettingFee.trim() || null,
            management_fee_rate: fields.managementRate,
            market_rent_amount: fields.marketRent.trim() || null,
            notes: fields.notes || null,
            rental_share_percentage:
              fields.scope === 'WHOLE' ? '100' : fields.rentalShare,
            vacancy_rate: fields.vacancyRate,
          }),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      ),
    onSuccess: async () => {
      form.reset(defaults());
      setDialogOpen(false);
      notify('Rental arrangement saved', 'success');
      await queryClient.invalidateQueries({
        queryKey: ['property-rental-profiles', propertyId],
      });
    },
  });
  const columns: DataColumn<RentalProfile>[] = [
    { key: 'name', label: 'Rental area', render: (row) => row.display_name },
    {
      key: 'share',
      label: 'Property share',
      render: (row) => `${row.rental_share_percentage}%`,
    },
    {
      key: 'rent',
      label: 'Rent charged',
      render: (row) =>
        `${formatCurrency(row.charged_rent_amount, currency)} ${row.frequency.toLowerCase()}`,
    },
    {
      key: 'dates',
      label: 'Effective dates',
      render: (row) =>
        `${formatDate(row.effective_from)} – ${row.effective_to ? formatDate(row.effective_to) : 'Ongoing'}`,
    },
  ];

  return (
    <Stack spacing={2}>
      <Stack
        direction="row"
        sx={{ alignItems: 'center', justifyContent: 'space-between' }}
      >
        <Typography variant="h2">Rental arrangements</Typography>
        {canEdit ? (
          <Button onClick={() => setDialogOpen(true)} variant="outlined">
            Add rental arrangement
          </Button>
        ) : null}
      </Stack>
      <Typography color="text.secondary">
        Record the whole home or separate rented portions such as a room, duplex
        unit or granny flat. The combined active shares cannot exceed 100%.
      </Typography>
      {profiles.isPending ? (
        <CircularProgress aria-label="Loading rental arrangements" size={24} />
      ) : profiles.error ? (
        <Alert
          action={
            <Button onClick={() => void profiles.refetch()}>Retry</Button>
          }
          severity="error"
        >
          Rental arrangements could not be loaded. {message(profiles.error)}
        </Alert>
      ) : profiles.data?.length ? (
        <DataTable
          caption="Rental arrangement history"
          columns={columns}
          getRowKey={(row) => row.id}
          rows={profiles.data}
        />
      ) : (
        <Alert severity="info">
          No rental arrangements have been added. Owner-occupied homes do not
          need one unless part of the property is rented out.
        </Alert>
      )}
      <Dialog
        fullWidth
        maxWidth="md"
        onClose={() => setDialogOpen(false)}
        open={dialogOpen}
      >
        <Stack
          component="form"
          onSubmit={(event) =>
            void form.handleSubmit((fields) => create.mutate(fields))(event)
          }
        >
          <DialogTitle>Add rental arrangement</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Alert severity="info">
                Use <strong>Whole property</strong> when one arrangement covers
                the entire home. Use <strong>Part of the property</strong> for a
                room or separate dwelling, and add each rented portion once.
              </Alert>
              <TextField
                label="Rental scope"
                select
                {...form.register('scope')}
              >
                <MenuItem value="WHOLE">Whole property</MenuItem>
                <MenuItem value="PARTIAL">Part of the property</MenuItem>
              </TextField>
              <TextField
                error={Boolean(form.formState.errors.displayName)}
                helperText={form.formState.errors.displayName?.message}
                label="Rental area name"
                placeholder={
                  scope === 'WHOLE' ? 'Whole home' : 'Granny flat or spare room'
                }
                {...form.register('displayName')}
              />
              {scope === 'PARTIAL' ? (
                <TextField
                  error={Boolean(form.formState.errors.rentalShare)}
                  helperText={
                    form.formState.errors.rentalShare?.message ??
                    'Approximate portion of the property covered by this arrangement'
                  }
                  label="Property share (%)"
                  {...form.register('rentalShare')}
                />
              ) : null}
              <Stack direction="row" spacing={2}>
                <TextField
                  error={Boolean(form.formState.errors.chargedRent)}
                  fullWidth
                  helperText={form.formState.errors.chargedRent?.message}
                  label={`Rent charged (${currency})`}
                  {...form.register('chargedRent')}
                />
                <TextField
                  fullWidth
                  label="Frequency"
                  select
                  {...form.register('frequency')}
                >
                  {frequencies.map(([value, label]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <TextField
                error={Boolean(form.formState.errors.marketRent)}
                helperText={
                  form.formState.errors.marketRent?.message ??
                  'Optional comparison for family or discounted arrangements'
                }
                label={`Comparable market rent (${currency}, optional)`}
                {...form.register('marketRent')}
              />
              <Stack direction="row" spacing={2}>
                <TextField
                  error={Boolean(form.formState.errors.vacancyRate)}
                  fullWidth
                  helperText={form.formState.errors.vacancyRate?.message}
                  label="Vacancy allowance (%)"
                  {...form.register('vacancyRate')}
                />
                <TextField
                  error={Boolean(form.formState.errors.managementRate)}
                  fullWidth
                  helperText={form.formState.errors.managementRate?.message}
                  label="Management fee (%)"
                  {...form.register('managementRate')}
                />
                <TextField
                  error={Boolean(form.formState.errors.lettingFee)}
                  fullWidth
                  helperText={form.formState.errors.lettingFee?.message}
                  label={`Letting fee (${currency}, optional)`}
                  {...form.register('lettingFee')}
                />
              </Stack>
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
              <AdvancedSection description="Notes are optional and intended for unusual household arrangements.">
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
              disabled={create.isPending}
              type="submit"
              variant="contained"
            >
              Save rental arrangement
            </Button>
          </DialogActions>
        </Stack>
      </Dialog>
    </Stack>
  );
}
