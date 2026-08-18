import { zodResolver } from '@hookform/resolvers/zod';
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
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Cashflow = components['schemas']['PropertyCashflowRead'];
type Expense = components['schemas']['PropertyExpenseRead'];
type Frequency = components['schemas']['PaymentFrequency'];
type Lookup = components['schemas']['LookupRead'];

const frequencies: Array<{ label: string; value: Frequency }> = [
  { label: 'Weekly', value: 'WEEKLY' },
  { label: 'Fortnightly', value: 'FORTNIGHTLY' },
  { label: 'Monthly', value: 'MONTHLY' },
  { label: 'Quarterly', value: 'QUARTERLY' },
  { label: 'Annual', value: 'ANNUAL' },
  { label: 'One-off', value: 'ONCE' },
];

const expenseSchema = z
  .object({
    amount: z
      .string()
      .refine(
        (value) =>
          value.trim() !== '' &&
          Number.isFinite(Number(value)) &&
          Number(value) >= 0,
        'Enter an amount of zero or more',
      ),
    displayName: z.string().trim().min(1, 'Enter a name').max(200),
    effectiveFrom: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a start date'),
    effectiveTo: z.string(),
    expenseTypeId: z.string().min(1, 'Choose an expense type'),
    frequency: z.enum([
      'WEEKLY',
      'FORTNIGHTLY',
      'MONTHLY',
      'QUARTERLY',
      'ANNUAL',
      'ONCE',
    ]),
    isRentalExpense: z.enum(['true', 'false']),
    notes: z.string().trim().max(2000),
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
      fields.frequency === 'ONCE' &&
      fields.effectiveTo &&
      fields.effectiveTo !== fields.effectiveFrom
    ) {
      context.addIssue({
        code: 'custom',
        message: 'A one-off expense cannot span a date range',
        path: ['effectiveTo'],
      });
    }
  });

type ExpenseFields = z.infer<typeof expenseSchema>;

function defaults(): ExpenseFields {
  return {
    amount: '',
    displayName: '',
    effectiveFrom: localCalendarDate(),
    effectiveTo: '',
    expenseTypeId: '',
    frequency: 'ANNUAL',
    isRentalExpense: 'false',
    notes: '',
  };
}

function startOfYear() {
  return `${localCalendarDate().slice(0, 4)}-01-01`;
}

function endOfYear() {
  return `${localCalendarDate().slice(0, 4)}-12-31`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function SummaryAmount({
  currency,
  label,
  value,
}: {
  currency: string;
  label: string;
  value: string;
}) {
  return (
    <Paper sx={{ flex: '1 1 180px', p: 2 }} variant="outlined">
      <Typography color="text.secondary" variant="body2">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }} variant="h6">
        {formatCurrency(value, currency)}
      </Typography>
    </Paper>
  );
}

export function RentalCashflowPanel({
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
  const [editing, setEditing] = useState<Expense | null>(null);
  const [deleting, setDeleting] = useState<Expense | null>(null);
  const [fromDate, setFromDate] = useState(startOfYear());
  const [toDate, setToDate] = useState(endOfYear());
  const [draftFrom, setDraftFrom] = useState(fromDate);
  const [draftTo, setDraftTo] = useState(toDate);
  const [dateError, setDateError] = useState('');
  const form = useForm<ExpenseFields>({
    defaultValues: defaults(),
    resolver: zodResolver(expenseSchema),
  });
  const frequency = useWatch({ control: form.control, name: 'frequency' });
  const expenseTypeId = useWatch({
    control: form.control,
    name: 'expenseTypeId',
  });
  const isRentalExpense = useWatch({
    control: form.control,
    name: 'isRentalExpense',
  });
  useEffect(() => {
    if (frequency === 'ONCE') form.setValue('effectiveTo', '');
  }, [form, frequency]);

  const expenses = useQuery({
    queryFn: () =>
      apiRequest<Expense[]>(`/api/v1/properties/${propertyId}/expenses`),
    queryKey: ['property-expenses', propertyId],
    retry: false,
  });
  const expenseTypes = useQuery({
    queryFn: () =>
      apiRequest<Lookup[]>('/api/v1/lookups/property_expense_type'),
    queryKey: ['lookups', 'property_expense_type'],
    retry: false,
  });
  const cashflow = useQuery({
    queryFn: () =>
      apiRequest<Cashflow>(
        `/api/v1/properties/${propertyId}/cashflow?from_date=${fromDate}&to_date=${toDate}`,
      ),
    queryKey: ['property-cashflow', propertyId, fromDate, toDate],
    retry: false,
  });

  const save = useMutation({
    mutationFn: (fields: ExpenseFields) =>
      apiRequest<Expense>(
        `/api/v1/properties/${propertyId}/expenses${editing ? `/${editing.id}` : ''}`,
        {
          body: JSON.stringify({
            amount: fields.amount,
            display_name: fields.displayName,
            effective_from: fields.effectiveFrom,
            effective_to: fields.effectiveTo || null,
            expense_type_id: fields.expenseTypeId,
            frequency: fields.frequency,
            is_rental_expense: fields.isRentalExpense === 'true',
            notes: fields.notes || null,
          }),
          csrfToken: auth.csrfToken(),
          method: editing ? 'PATCH' : 'POST',
        },
      ),
    onSuccess: async () => {
      setDialogOpen(false);
      setEditing(null);
      form.reset(defaults());
      notify(
        editing ? 'Property expense updated' : 'Property expense added',
        'success',
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['property-expenses', propertyId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['property-cashflow', propertyId],
        }),
      ]);
    },
  });
  const remove = useMutation({
    mutationFn: (expense: Expense) =>
      apiRequest<void>(
        `/api/v1/properties/${propertyId}/expenses/${expense.id}`,
        {
          csrfToken: auth.csrfToken(),
          method: 'DELETE',
        },
      ),
    onSuccess: async () => {
      setDeleting(null);
      notify('Property expense removed', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['property-expenses', propertyId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['property-cashflow', propertyId],
        }),
      ]);
    },
    onError: (error) => notify(errorMessage(error), 'error'),
  });

  const openCreate = () => {
    save.reset();
    setEditing(null);
    form.reset(defaults());
    setDialogOpen(true);
  };
  const openEdit = (expense: Expense) => {
    save.reset();
    setEditing(expense);
    form.reset({
      amount: expense.amount,
      displayName: expense.display_name,
      effectiveFrom: expense.effective_from,
      effectiveTo: expense.effective_to ?? '',
      expenseTypeId: expense.expense_type_id,
      frequency: expense.frequency,
      isRentalExpense: expense.is_rental_expense ? 'true' : 'false',
      notes: expense.notes ?? '',
    });
    setDialogOpen(true);
  };
  const applyDates = () => {
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(draftFrom) ||
      !/^\d{4}-\d{2}-\d{2}$/.test(draftTo)
    ) {
      setDateError('Enter both dates');
      return;
    }
    if (draftTo < draftFrom) {
      setDateError('The end date cannot be before the start date');
      return;
    }
    setDateError('');
    if (draftFrom === fromDate && draftTo === toDate) void cashflow.refetch();
    else {
      setFromDate(draftFrom);
      setToDate(draftTo);
    }
  };
  const typeName = (id: string) =>
    expenseTypes.data?.find((item) => item.id === id)?.display_name ??
    'Unavailable type';
  const columns: DataColumn<Expense>[] = [
    { key: 'name', label: 'Expense', render: (row) => row.display_name },
    {
      key: 'type',
      label: 'Type',
      render: (row) => typeName(row.expense_type_id),
    },
    {
      key: 'amount',
      label: 'Amount',
      render: (row) =>
        `${formatCurrency(row.amount, currency)} ${row.frequency.toLowerCase()}`,
    },
    {
      key: 'scope',
      label: 'Applies to',
      render: (row) =>
        row.is_rental_expense ? 'Rented portion' : 'Whole property',
    },
    {
      key: 'dates',
      label: 'Effective dates',
      render: (row) =>
        `${formatDate(row.effective_from)} – ${row.effective_to ? formatDate(row.effective_to) : row.frequency === 'ONCE' ? 'One-off' : 'Ongoing'}`,
    },
    ...(canEdit
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (row: Expense) => (
              <Stack direction="row" spacing={1}>
                <Button onClick={() => openEdit(row)} size="small">
                  Correct or end
                </Button>
                <Button
                  color="error"
                  onClick={() => setDeleting(row)}
                  size="small"
                >
                  Remove
                </Button>
              </Stack>
            ),
          },
        ]
      : []),
  ];
  const dateDirty = draftFrom !== fromDate || draftTo !== toDate;
  const displayCurrency = cashflow.data?.currency ?? currency;

  return (
    <Stack spacing={3}>
      <Stack spacing={2}>
        <Stack
          direction="row"
          sx={{ alignItems: 'center', justifyContent: 'space-between' }}
        >
          <Typography variant="h2">Property expenses</Typography>
          {canEdit ? (
            <Button onClick={openCreate} variant="outlined">
              Add property expense
            </Button>
          ) : null}
        </Stack>
        <Typography color="text.secondary">
          Record costs for the whole property or costs that apply only while a
          rented portion is earning income.
        </Typography>
        {expenses.isPending || expenseTypes.isPending ? (
          <CircularProgress aria-label="Loading property expenses" size={24} />
        ) : expenses.error || expenseTypes.error ? (
          <Alert
            action={
              <Button
                onClick={() =>
                  void Promise.all([expenses.refetch(), expenseTypes.refetch()])
                }
              >
                Retry
              </Button>
            }
            severity="error"
          >
            Property expenses could not be loaded.{' '}
            {errorMessage(expenses.error ?? expenseTypes.error)}
          </Alert>
        ) : expenses.data?.length ? (
          <DataTable
            caption="Property expense history"
            columns={columns}
            getRowKey={(row) => row.id}
            rows={expenses.data}
          />
        ) : (
          <Alert severity="info">
            No property expenses have been recorded.
          </Alert>
        )}
      </Stack>

      <Stack spacing={2}>
        <Typography variant="h2">Rental cash flow</Typography>
        <Stack
          direction="row"
          spacing={2}
          sx={{ alignItems: 'flex-start', flexWrap: 'wrap' }}
        >
          <TextField
            label="From"
            onChange={(event) => setDraftFrom(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={draftFrom}
          />
          <TextField
            error={Boolean(dateError)}
            helperText={dateError}
            label="To"
            onChange={(event) => setDraftTo(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={draftTo}
          />
          <Button onClick={applyDates} variant="outlined">
            Refresh cash flow
          </Button>
        </Stack>
        {cashflow.isPending ? (
          <CircularProgress
            aria-label="Calculating rental cash flow"
            size={24}
          />
        ) : cashflow.error ? (
          <Alert
            action={
              <Button onClick={() => void cashflow.refetch()}>Retry</Button>
            }
            severity="error"
          >
            Rental cash flow could not be calculated.{' '}
            {errorMessage(cashflow.error)}
          </Alert>
        ) : cashflow.data ? (
          <Stack spacing={2}>
            <Alert severity={dateDirty ? 'info' : 'success'}>
              Results from {formatDate(cashflow.data.from_date)} to{' '}
              {formatDate(cashflow.data.to_date)}.
              {dateDirty
                ? ' The date range has changed; refresh to recalculate.'
                : ''}
            </Alert>
            <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
              <SummaryAmount
                currency={displayCurrency}
                label="Gross rent"
                value={cashflow.data.gross_rent}
              />
              <SummaryAmount
                currency={displayCurrency}
                label="Vacancy allowance"
                value={cashflow.data.vacancy_cost}
              />
              <SummaryAmount
                currency={displayCurrency}
                label="Management fees"
                value={cashflow.data.management_fee}
              />
              <SummaryAmount
                currency={displayCurrency}
                label="Letting fees"
                value={cashflow.data.letting_fees}
              />
              <SummaryAmount
                currency={displayCurrency}
                label="Property expenses"
                value={cashflow.data.property_expenses}
              />
              <SummaryAmount
                currency={displayCurrency}
                label="Net rental cash flow"
                value={cashflow.data.net_cashflow}
              />
            </Stack>
            <Typography>
              Rent was active for {cashflow.data.rental_days} days. Charged rent
              differs from comparable market rent by{' '}
              {formatCurrency(cashflow.data.rent_difference, displayCurrency)}.
              {cashflow.data.warnings.length ? (
                <Tooltip arrow title={cashflow.data.warnings.join(' ')}>
                  <IconButton
                    aria-label="Rental cash-flow assumptions"
                    size="small"
                  >
                    ⓘ
                  </IconButton>
                </Tooltip>
              ) : null}
            </Typography>
          </Stack>
        ) : null}
      </Stack>

      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={() => {
          setDialogOpen(false);
          setEditing(null);
          save.reset();
        }}
        open={dialogOpen}
      >
        <Stack
          component="form"
          onSubmit={(event) =>
            void form.handleSubmit((fields) => save.mutate(fields))(event)
          }
        >
          <DialogTitle>
            {editing
              ? 'Correct or end property expense'
              : 'Add property expense'}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                error={Boolean(form.formState.errors.displayName)}
                helperText={form.formState.errors.displayName?.message}
                label="Expense name"
                {...form.register('displayName')}
              />
              <TextField
                disabled={expenseTypes.isPending || Boolean(expenseTypes.error)}
                error={Boolean(form.formState.errors.expenseTypeId)}
                helperText={form.formState.errors.expenseTypeId?.message}
                label="Expense type"
                select
                value={expenseTypeId}
                {...form.register('expenseTypeId')}
              >
                {(expenseTypes.data ?? []).map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.display_name}
                  </MenuItem>
                ))}
              </TextField>
              <Stack direction="row" spacing={2}>
                <TextField
                  error={Boolean(form.formState.errors.amount)}
                  fullWidth
                  helperText={form.formState.errors.amount?.message}
                  label={`Amount (${currency})`}
                  {...form.register('amount')}
                />
                <TextField
                  fullWidth
                  label="Frequency"
                  select
                  value={frequency}
                  {...form.register('frequency')}
                >
                  {frequencies.map((item) => (
                    <MenuItem key={item.value} value={item.value}>
                      {item.label}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <TextField
                label="Cost scope"
                select
                value={isRentalExpense}
                {...form.register('isRentalExpense')}
              >
                <MenuItem value="false">Whole property</MenuItem>
                <MenuItem value="true">Rented portion only</MenuItem>
              </TextField>
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
                {frequency !== 'ONCE' ? (
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
                ) : null}
              </Stack>
              <AdvancedSection description="Notes are optional and intended for unusual property costs.">
                <TextField
                  label="Notes (optional)"
                  multiline
                  minRows={2}
                  {...form.register('notes')}
                />
              </AdvancedSection>
              {save.error ? (
                <Alert severity="error">
                  Expense could not be saved. {errorMessage(save.error)}
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button
              disabled={save.isPending}
              onClick={() => {
                setDialogOpen(false);
                setEditing(null);
                save.reset();
              }}
            >
              Cancel
            </Button>
            <Button
              disabled={
                save.isPending ||
                expenseTypes.isPending ||
                Boolean(expenseTypes.error)
              }
              type="submit"
              variant="contained"
            >
              Save expense
            </Button>
          </DialogActions>
        </Stack>
      </Dialog>
      <ConfirmDialog
        confirmLabel="Remove expense"
        description={`Remove ${deleting?.display_name ?? 'this expense'}? The cash-flow calculation will no longer include it.`}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && remove.mutate(deleting)}
        open={deleting !== null}
        pending={remove.isPending}
        title="Remove property expense?"
      />
    </Stack>
  );
}
