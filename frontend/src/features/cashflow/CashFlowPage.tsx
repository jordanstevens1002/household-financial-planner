import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Box,
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
import { Link } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { useHousehold } from '../households/HouseholdContext';
import { localCalendarDate } from '../people/localDate';
import { expenseSchema, type ExpenseFields } from './expenseValidation';
import { CashFlowSummary } from './CashFlowSummary';

type Access = components['schemas']['HouseholdAccessRead'];
type Expense = components['schemas']['HouseholdExpenseRead'];
type Frequency = components['schemas']['PaymentFrequency'];
type Lookup = components['schemas']['LookupRead'];
type Person = components['schemas']['PersonRead'];

const frequencies: { label: string; value: Frequency }[] = [
  { label: 'Weekly', value: 'WEEKLY' },
  { label: 'Fortnightly', value: 'FORTNIGHTLY' },
  { label: 'Monthly', value: 'MONTHLY' },
  { label: 'Quarterly', value: 'QUARTERLY' },
  { label: 'Annual', value: 'ANNUAL' },
  { label: 'One-off', value: 'ONCE' },
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

const defaults = (): ExpenseFields => ({
  amount: '',
  annualGrowthRate: '',
  categoryId: '',
  displayName: '',
  effectiveFrom: localCalendarDate(),
  effectiveTo: '',
  frequency: 'MONTHLY',
  isEssential: 'true',
  notes: '',
  personId: '',
});

function expenseFields(expense: Expense): ExpenseFields {
  return {
    amount: expense.amount,
    annualGrowthRate: expense.annual_growth_rate ?? '',
    categoryId: expense.category_id,
    displayName: expense.display_name,
    effectiveFrom: expense.effective_from,
    effectiveTo: expense.effective_to ?? '',
    frequency: expense.frequency,
    isEssential: expense.is_essential ? 'true' : 'false',
    notes: expense.notes ?? '',
    personId: expense.person_id ?? '',
  };
}

function requestBody(fields: ExpenseFields) {
  return {
    amount: fields.amount,
    annual_growth_rate:
      fields.frequency === 'ONCE' ? null : fields.annualGrowthRate || null,
    category_id: fields.categoryId,
    display_name: fields.displayName,
    effective_from: fields.effectiveFrom,
    effective_to: fields.effectiveTo || null,
    frequency: fields.frequency,
    is_essential: fields.isEssential === 'true',
    notes: fields.notes || null,
    person_id: fields.personId || null,
  };
}

export function CashFlowPage() {
  const auth = useAuth();
  const household = useHousehold();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [deleting, setDeleting] = useState<Expense | null>(null);
  const householdId = household.selected?.id;
  const expenses = useQuery({
    enabled: Boolean(householdId),
    queryFn: () =>
      apiRequest<Expense[]>(`/api/v1/households/${householdId}/expenses`),
    queryKey: ['household-expenses', householdId],
    retry: false,
  });
  const access = useQuery({
    enabled: Boolean(householdId),
    queryFn: () =>
      apiRequest<Access>(`/api/v1/households/${householdId}/access`),
    queryKey: ['household-access', householdId],
    retry: false,
  });
  const categories = useQuery({
    enabled: Boolean(householdId),
    queryFn: () =>
      apiRequest<Lookup[]>('/api/v1/lookups/household_expense_type'),
    queryKey: ['lookups', 'household_expense_type'],
    retry: false,
  });
  const people = useQuery({
    enabled: Boolean(householdId),
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const form = useForm<ExpenseFields>({
    defaultValues: defaults(),
    resolver: zodResolver(expenseSchema),
  });
  const frequency = useWatch({ control: form.control, name: 'frequency' });
  useEffect(() => {
    if (frequency === 'ONCE') {
      form.setValue('annualGrowthRate', '', { shouldValidate: true });
    }
  }, [form, frequency]);
  useEffect(() => {
    if (people.error) {
      form.setValue('personId', '');
    }
  }, [form, people.error]);
  const saveExpense = useMutation({
    mutationFn: (fields: ExpenseFields) =>
      apiRequest<Expense>(
        `/api/v1/households/${householdId}/expenses${editing ? `/${editing.id}` : ''}`,
        {
          body: JSON.stringify(requestBody(fields)),
          csrfToken: auth.csrfToken(),
          method: editing ? 'PATCH' : 'POST',
        },
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData<Expense[]>(
        ['household-expenses', householdId],
        (current) =>
          editing
            ? (current ?? []).map((item) =>
                item.id === saved.id ? saved : item,
              )
            : [...(current ?? []), saved],
      );
      void queryClient.invalidateQueries({
        queryKey: ['household-cashflow', householdId],
      });
      setCreateOpen(false);
      setEditing(null);
      form.reset(defaults());
      notify(editing ? 'Expense updated' : 'Expense added', 'success');
    },
  });
  const deleteExpense = useMutation({
    mutationFn: (expense: Expense) =>
      apiRequest<void>(
        `/api/v1/households/${householdId}/expenses/${expense.id}`,
        { csrfToken: auth.csrfToken(), method: 'DELETE' },
      ),
    onSuccess: (_, deleted) => {
      queryClient.setQueryData<Expense[]>(
        ['household-expenses', householdId],
        (current) => (current ?? []).filter((item) => item.id !== deleted.id),
      );
      void queryClient.invalidateQueries({
        queryKey: ['household-cashflow', householdId],
      });
      setDeleting(null);
      notify('Expense removed', 'success');
    },
  });

  if (!household.selected) {
    return (
      <Stack spacing={3}>
        <Typography component="h1" variant="h4">
          Cash flow
        </Typography>
        <EmptyState
          description="Choose a household before recording its expenses."
          title="No household selected"
        />
        <Button
          component={Link}
          sx={{ alignSelf: 'flex-start' }}
          to="/households"
          variant="contained"
        >
          Choose a household
        </Button>
      </Stack>
    );
  }
  if (expenses.isPending || access.isPending) {
    return <CircularProgress aria-label="Loading household expenses" />;
  }
  if (expenses.error || access.error) {
    return (
      <Alert severity="error">
        Could not load household expenses.{' '}
        {errorMessage(expenses.error ?? access.error)}
      </Alert>
    );
  }

  const selectedHousehold = household.selected;
  const canEdit = access.data?.can_edit === true;
  const categoryName = (id: string) =>
    categories.data?.find((item) => item.id === id)?.display_name ??
    'Unavailable category';
  const personName = (id: string | null | undefined) =>
    id
      ? (people.data?.find((item) => item.id === id)?.display_name ??
        'Unavailable person')
      : 'Whole household';
  const openCreate = () => {
    setEditing(null);
    form.reset(defaults());
    setCreateOpen(true);
  };
  const openEdit = (expense: Expense) => {
    setCreateOpen(false);
    setEditing(expense);
    form.reset(expenseFields(expense));
  };
  const closeDialog = () => {
    setCreateOpen(false);
    setEditing(null);
    saveExpense.reset();
  };
  const columns: DataColumn<Expense>[] = [
    { key: 'name', label: 'Expense', render: (row) => row.display_name },
    {
      key: 'amount',
      label: 'Amount',
      render: (row) => formatCurrency(row.amount, selectedHousehold.currency),
    },
    {
      key: 'frequency',
      label: 'Frequency',
      render: (row) =>
        frequencies.find((item) => item.value === row.frequency)?.label ??
        row.frequency,
    },
    {
      key: 'category',
      label: 'Category',
      render: (row) => categoryName(row.category_id),
    },
    {
      key: 'person',
      label: 'Paid for by',
      render: (row) => personName(row.person_id),
    },
    {
      key: 'effective',
      label: 'Effective range',
      render: (row) =>
        `${formatDate(row.effective_from)} – ${row.effective_to ? formatDate(row.effective_to) : 'Ongoing'}`,
    },
    {
      key: 'details',
      label: 'Details',
      render: (row) =>
        `${row.is_essential ? 'Essential' : 'Optional'} · ${row.annual_growth_rate === null ? 'No growth' : `${row.annual_growth_rate}% growth`}`,
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) =>
        canEdit ? (
          <Stack direction="row" spacing={1}>
            <Button onClick={() => openEdit(row)} size="small">
              Edit
            </Button>
            <Button color="error" onClick={() => setDeleting(row)} size="small">
              Remove
            </Button>
          </Stack>
        ) : (
          'View only'
        ),
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Cash flow
        </Typography>
        <Typography color="text.secondary">
          Review income, spending and loan repayments together, then record
          household expenses as dated recurring or one-off costs.
        </Typography>
      </Box>
      <CashFlowSummary
        currency={selectedHousehold.currency}
        householdId={selectedHousehold.id}
      />
      <Typography variant="h2">Household expenses</Typography>
      {canEdit ? (
        <Button
          onClick={openCreate}
          sx={{ alignSelf: 'flex-start' }}
          variant="contained"
        >
          Add expense
        </Button>
      ) : (
        <Alert severity="info">
          You have view-only access to household expenses.
        </Alert>
      )}
      {expenses.data?.length ? (
        <DataTable
          caption="Household expenses"
          columns={columns}
          getRowKey={(row) => row.id}
          rows={expenses.data}
        />
      ) : (
        <EmptyState
          description="Add regular bills, groceries or one-off household costs."
          title="No household expenses yet"
        />
      )}
      {deleteExpense.error ? (
        <Alert severity="error">
          Expense could not be removed. {errorMessage(deleteExpense.error)}
        </Alert>
      ) : null}
      <Dialog
        fullWidth
        maxWidth="md"
        onClose={closeDialog}
        open={createOpen || editing !== null}
      >
        <form
          onSubmit={(event) =>
            void form.handleSubmit((fields) => saveExpense.mutate(fields))(
              event,
            )
          }
        >
          <DialogTitle>
            {editing ? 'Edit household expense' : 'Add household expense'}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              {categories.error ? (
                <Alert
                  action={
                    <Button
                      color="inherit"
                      onClick={() => void categories.refetch()}
                    >
                      Retry
                    </Button>
                  }
                  severity="error"
                >
                  Expense categories could not be loaded.{' '}
                  {errorMessage(categories.error)}
                </Alert>
              ) : null}
              {people.error ? (
                <Alert severity="warning">
                  People could not be loaded, so this expense will apply to the
                  whole household. {errorMessage(people.error)}
                </Alert>
              ) : null}
              <TextField
                error={Boolean(form.formState.errors.displayName)}
                helperText={form.formState.errors.displayName?.message}
                label="Expense name"
                {...form.register('displayName')}
              />
              <TextField
                disabled={categories.isPending || Boolean(categories.error)}
                error={Boolean(form.formState.errors.categoryId)}
                helperText={form.formState.errors.categoryId?.message}
                label="Category"
                select
                {...form.register('categoryId')}
              >
                {(categories.data ?? []).map((category) => (
                  <MenuItem key={category.id} value={category.id}>
                    {category.display_name}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                error={Boolean(form.formState.errors.amount)}
                helperText={form.formState.errors.amount?.message}
                label={`Amount (${selectedHousehold.currency})`}
                {...form.register('amount')}
              />
              <TextField
                label="Frequency"
                select
                {...form.register('frequency')}
              >
                {frequencies.map((frequency) => (
                  <MenuItem key={frequency.value} value={frequency.value}>
                    {frequency.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                label="Essential expense"
                select
                {...form.register('isEssential')}
              >
                <MenuItem value="true">Yes</MenuItem>
                <MenuItem value="false">No</MenuItem>
              </TextField>
              <TextField
                disabled={people.isPending || Boolean(people.error)}
                label="Paid for by (optional)"
                select
                {...form.register('personId')}
              >
                <MenuItem value="">Whole household</MenuItem>
                {(people.data ?? []).map((person) => (
                  <MenuItem key={person.id} value={person.id}>
                    {person.display_name}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                error={Boolean(form.formState.errors.effectiveFrom)}
                helperText={form.formState.errors.effectiveFrom?.message}
                label="Effective from"
                type="date"
                {...form.register('effectiveFrom')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                error={Boolean(form.formState.errors.effectiveTo)}
                helperText={form.formState.errors.effectiveTo?.message}
                label="Effective to (optional)"
                type="date"
                {...form.register('effectiveTo')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <AdvancedSection description="Growth assumptions and notes are optional planning details.">
                {frequency !== 'ONCE' ? (
                  <TextField
                    error={Boolean(form.formState.errors.annualGrowthRate)}
                    helperText={form.formState.errors.annualGrowthRate?.message}
                    label="Annual growth rate % (optional)"
                    {...form.register('annualGrowthRate')}
                  />
                ) : (
                  <Alert severity="info">
                    Growth does not apply to a one-off expense.
                  </Alert>
                )}
                <TextField
                  label="Notes (optional)"
                  multiline
                  minRows={2}
                  {...form.register('notes')}
                />
              </AdvancedSection>
              {saveExpense.error ? (
                <Alert severity="error">
                  Expense could not be saved. {errorMessage(saveExpense.error)}
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={closeDialog}>Cancel</Button>
            <Button
              disabled={
                saveExpense.isPending ||
                categories.isPending ||
                !categories.data?.length
              }
              type="submit"
              variant="contained"
            >
              {saveExpense.isPending
                ? 'Saving…'
                : editing
                  ? 'Save changes'
                  : 'Add expense'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
      <ConfirmDialog
        confirmLabel="Remove expense"
        description={`Remove ${deleting?.display_name ?? 'this expense'}? It will no longer be included in cash-flow calculations.`}
        onCancel={() => setDeleting(null)}
        onConfirm={() => {
          if (deleting) deleteExpense.mutate(deleting);
        }}
        open={deleting !== null}
        pending={deleteExpense.isPending}
        title="Remove household expense?"
      />
    </Stack>
  );
}
