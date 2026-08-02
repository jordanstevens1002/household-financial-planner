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
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { useHousehold } from '../households/HouseholdContext';
import { localCalendarDate } from '../people/localDate';
import { expenseSchema, type ExpenseFields } from './expenseValidation';

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

export function CashFlowPage() {
  const auth = useAuth();
  const household = useHousehold();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [createOpen, setCreateOpen] = useState(false);
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
    enabled: createOpen,
    queryFn: () =>
      apiRequest<Lookup[]>('/api/v1/lookups/household_expense_type'),
    queryKey: ['lookups', 'household_expense_type'],
    retry: false,
  });
  const people = useQuery({
    enabled: createOpen && Boolean(householdId),
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const form = useForm<ExpenseFields>({
    defaultValues: defaults(),
    resolver: zodResolver(expenseSchema),
  });
  const createExpense = useMutation({
    mutationFn: (fields: ExpenseFields) =>
      apiRequest<Expense>(`/api/v1/households/${householdId}/expenses`, {
        body: JSON.stringify({
          amount: fields.amount,
          annual_growth_rate: fields.annualGrowthRate || null,
          category_id: fields.categoryId,
          display_name: fields.displayName,
          effective_from: fields.effectiveFrom,
          effective_to: fields.effectiveTo || null,
          frequency: fields.frequency,
          is_essential: fields.isEssential === 'true',
          notes: fields.notes || null,
          person_id: fields.personId || null,
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: (created) => {
      queryClient.setQueryData<Expense[]>(
        ['household-expenses', householdId],
        (current) => [...(current ?? []), created],
      );
      setCreateOpen(false);
      form.reset(defaults());
      notify('Expense added', 'success');
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
      key: 'essential',
      label: 'Essential',
      render: (row) => (row.is_essential ? 'Yes' : 'No'),
    },
    {
      key: 'from',
      label: 'Effective from',
      render: (row) => formatDate(row.effective_from),
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Cash flow
        </Typography>
        <Typography color="text.secondary">
          Record household spending as dated recurring or one-off expenses.
          Calculated summaries will be added in the next review slice.
        </Typography>
      </Box>
      {access.data?.can_edit ? (
        <Button
          onClick={() => setCreateOpen(true)}
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
      <Dialog
        fullWidth
        maxWidth="md"
        onClose={() => setCreateOpen(false)}
        open={createOpen}
      >
        <form
          onSubmit={(event) =>
            void form.handleSubmit((fields) => createExpense.mutate(fields))(
              event,
            )
          }
        >
          <DialogTitle>Add household expense</DialogTitle>
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
                <Alert severity="error">
                  People could not be loaded. {errorMessage(people.error)}
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
                <TextField
                  error={Boolean(form.formState.errors.annualGrowthRate)}
                  helperText={form.formState.errors.annualGrowthRate?.message}
                  label="Annual growth rate % (optional)"
                  {...form.register('annualGrowthRate')}
                />
                <TextField
                  label="Notes (optional)"
                  multiline
                  minRows={2}
                  {...form.register('notes')}
                />
              </AdvancedSection>
              {createExpense.error ? (
                <Alert severity="error">
                  Expense could not be added.{' '}
                  {errorMessage(createExpense.error)}
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={
                createExpense.isPending ||
                categories.isPending ||
                !categories.data?.length ||
                Boolean(people.error)
              }
              type="submit"
              variant="contained"
            >
              {createExpense.isPending ? 'Adding…' : 'Add expense'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Stack>
  );
}
