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
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { Link } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { loadSelection } from '../../app/selectionStorage';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { useHousehold } from '../households/HouseholdContext';
import { localCalendarDate } from '../people/localDate';
import { incomeSchema, type IncomeFields } from './incomeValidation';
import { TaxProfilesPanel } from './TaxProfilesPanel';

type Access = components['schemas']['HouseholdAccessRead'];
type Income = components['schemas']['IncomeSourceRead'];
type Lookup = components['schemas']['LookupRead'];
type Person = components['schemas']['PersonRead'];
type Frequency = components['schemas']['PaymentFrequency'];

const frequencies: { label: string; value: Frequency }[] = [
  { label: 'Weekly', value: 'WEEKLY' },
  { label: 'Fortnightly', value: 'FORTNIGHTLY' },
  { label: 'Monthly', value: 'MONTHLY' },
  { label: 'Quarterly', value: 'QUARTERLY' },
  { label: 'Annual', value: 'ANNUAL' },
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function IncomePage() {
  const auth = useAuth();
  const household = useHousehold();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [createOpen, setCreateOpen] = useState(false);
  const [section, setSection] = useState<'income' | 'tax'>('income');
  const selectedPersonId = loadSelection('person');
  const people = useQuery({
    enabled: household.selected !== null,
    queryFn: () =>
      apiRequest<Person[]>(
        `/api/v1/households/${household.selected!.id}/people`,
      ),
    queryKey: ['people', household.selected?.id],
    retry: false,
  });
  const person = people.data?.find((item) => item.id === selectedPersonId);
  const access = useQuery({
    enabled: household.selected !== null,
    queryFn: () =>
      apiRequest<Access>(`/api/v1/households/${household.selected!.id}/access`),
    queryKey: ['household-access', household.selected?.id],
    retry: false,
  });
  const incomeSources = useQuery({
    enabled: person !== undefined,
    queryFn: () =>
      apiRequest<Income[]>(`/api/v1/people/${person!.id}/income-sources`),
    queryKey: ['income-sources', person?.id],
    retry: false,
  });
  const incomeTypes = useQuery({
    enabled: createOpen,
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/income_type'),
    queryKey: ['lookups', 'income_type'],
    retry: false,
  });
  const form = useForm<IncomeFields>({
    defaultValues: {
      annualGrowthRate: '',
      displayName: '',
      effectiveFrom: localCalendarDate(),
      effectiveTo: '',
      frequency: 'MONTHLY',
      grossAmount: '',
      incomeTypeId: '',
      notes: '',
      salarySacrificeAmount: '',
      taxable: 'true',
    },
    resolver: zodResolver(incomeSchema),
  });
  const createIncome = useMutation({
    mutationFn: (fields: IncomeFields) =>
      apiRequest<Income>(`/api/v1/people/${person!.id}/income-sources`, {
        body: JSON.stringify({
          annual_growth_rate: fields.annualGrowthRate || null,
          display_name: fields.displayName,
          effective_from: fields.effectiveFrom,
          effective_to: fields.effectiveTo || null,
          frequency: fields.frequency,
          gross_amount: fields.grossAmount,
          income_type_id: fields.incomeTypeId,
          notes: fields.notes || null,
          salary_sacrifice_amount: fields.salarySacrificeAmount || null,
          taxable: fields.taxable === 'true',
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: (created) => {
      queryClient.setQueryData<Income[]>(
        ['income-sources', person!.id],
        (current) => [...(current ?? []), created],
      );
      setCreateOpen(false);
      form.reset({
        annualGrowthRate: '',
        displayName: '',
        effectiveFrom: localCalendarDate(),
        effectiveTo: '',
        frequency: 'MONTHLY',
        grossAmount: '',
        incomeTypeId: '',
        notes: '',
        salarySacrificeAmount: '',
        taxable: 'true',
      });
      notify('Income source added', 'success');
    },
  });

  if (!household.selected) {
    return (
      <Stack spacing={3}>
        <Typography component="h1" variant="h4">
          Income &amp; tax
        </Typography>
        <EmptyState
          description={
            'Choose a household and person before recording their income.'
          }
          title="No person selected"
        />
        <Button
          component={Link}
          sx={{ alignSelf: 'flex-start' }}
          to="/people"
          variant="contained"
        >
          Choose a person
        </Button>
      </Stack>
    );
  }
  if (people.isPending) {
    return <CircularProgress aria-label="Loading income sources" />;
  }
  if (people.error) {
    return (
      <Alert severity="error">
        Could not load people for income. {errorMessage(people.error)}
      </Alert>
    );
  }
  if (!person) {
    return (
      <Stack spacing={3}>
        <Typography component="h1" variant="h4">
          Income &amp; tax
        </Typography>
        <EmptyState
          description="Choose a person before recording their income."
          title="No person selected"
        />
        <Button
          component={Link}
          sx={{ alignSelf: 'flex-start' }}
          to="/people"
          variant="contained"
        >
          Choose a person
        </Button>
      </Stack>
    );
  }
  if (access.isPending) {
    return <CircularProgress aria-label="Loading income access" />;
  }
  if (access.error) {
    return (
      <Alert severity="error">
        Could not load income access. {errorMessage(access.error)}
      </Alert>
    );
  }

  const columns: DataColumn<Income>[] = [
    { key: 'name', label: 'Income', render: (row) => row.display_name },
    {
      key: 'gross',
      label: 'Gross amount',
      render: (row) =>
        formatCurrency(row.gross_amount, household.selected!.currency),
    },
    {
      key: 'frequency',
      label: 'Frequency',
      render: (row) =>
        frequencies.find((item) => item.value === row.frequency)?.label ??
        row.frequency,
    },
    {
      key: 'taxable',
      label: 'Taxable',
      render: (row) => (row.taxable ? 'Yes' : 'No'),
    },
    {
      key: 'effective',
      label: 'Effective from',
      render: (row) => formatDate(row.effective_from),
    },
  ];
  const canEdit = access.data?.can_edit === true;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Income &amp; tax
        </Typography>
        <Typography color="text.secondary">
          Record recurring income for {person.display_name} using dated values
          so future projections can resolve the correct amount.
        </Typography>
      </Box>
      <Tabs
        onChange={(_, value: 'income' | 'tax') => setSection(value)}
        value={section}
      >
        <Tab label="Income sources" value="income" />
        <Tab label="Tax settings" value="tax" />
      </Tabs>
      {section === 'income' ? (
        <Stack spacing={2}>
          {canEdit ? (
            <Button
              onClick={() => setCreateOpen(true)}
              sx={{ alignSelf: 'flex-start' }}
              variant="contained"
            >
              Add income source
            </Button>
          ) : (
            <Alert severity="info">
              You have view-only access to this person's income sources.
            </Alert>
          )}
          {incomeSources.isPending ? (
            <CircularProgress aria-label="Loading income sources" />
          ) : incomeSources.error ? (
            <Alert severity="error">
              Could not load income sources. {errorMessage(incomeSources.error)}
            </Alert>
          ) : incomeSources.data?.length ? (
            <DataTable
              caption="Income sources"
              columns={columns}
              getRowKey={(row) => row.id}
              rows={incomeSources.data}
            />
          ) : (
            <EmptyState
              description="Add recurring earnings such as salary, benefits or investment income."
              title="No income sources yet"
            />
          )}
        </Stack>
      ) : (
        <TaxProfilesPanel canEdit={canEdit} personId={person.id} />
      )}

      <Dialog fullWidth open={createOpen} onClose={() => setCreateOpen(false)}>
        <DialogTitle>Add income source</DialogTitle>
        <Box
          component="form"
          onSubmit={(event) =>
            void form.handleSubmit((fields) => createIncome.mutate(fields))(
              event,
            )
          }
        >
          <DialogContent>
            <Stack spacing={2}>
              {incomeTypes.isPending ? (
                <CircularProgress aria-label="Loading income types" size={24} />
              ) : incomeTypes.error ? (
                <Alert
                  action={
                    <Button
                      color="inherit"
                      onClick={() => void incomeTypes.refetch()}
                      size="small"
                    >
                      Retry
                    </Button>
                  }
                  severity="error"
                >
                  Could not load income types. {errorMessage(incomeTypes.error)}
                </Alert>
              ) : incomeTypes.data?.length ? (
                <TextField
                  defaultValue=""
                  error={Boolean(form.formState.errors.incomeTypeId)}
                  helperText={form.formState.errors.incomeTypeId?.message}
                  label="Income type"
                  select
                  {...form.register('incomeTypeId')}
                >
                  {incomeTypes.data.map((item) => (
                    <MenuItem key={item.id} value={item.id}>
                      {item.display_name}
                    </MenuItem>
                  ))}
                </TextField>
              ) : (
                <Alert severity="warning">
                  No active income types are installed. Add one before recording
                  income.
                </Alert>
              )}
              <TextField
                error={Boolean(form.formState.errors.displayName)}
                helperText={form.formState.errors.displayName?.message}
                label="Income name"
                {...form.register('displayName')}
              />
              <TextField
                error={Boolean(form.formState.errors.grossAmount)}
                helperText={form.formState.errors.grossAmount?.message}
                label="Gross amount"
                {...form.register('grossAmount')}
              />
              <TextField
                defaultValue="MONTHLY"
                label="Frequency"
                select
                {...form.register('frequency')}
              >
                {frequencies.map((item) => (
                  <MenuItem key={item.value} value={item.value}>
                    {item.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                defaultValue="true"
                label="Tax treatment"
                select
                {...form.register('taxable')}
              >
                <MenuItem value="true">Taxable</MenuItem>
                <MenuItem value="false">Not taxable</MenuItem>
              </TextField>
              <TextField
                error={Boolean(form.formState.errors.effectiveFrom)}
                helperText={form.formState.errors.effectiveFrom?.message}
                label="Effective from"
                {...form.register('effectiveFrom')}
              />
              <TextField
                error={Boolean(form.formState.errors.effectiveTo)}
                helperText={form.formState.errors.effectiveTo?.message}
                label="Effective to (optional)"
                {...form.register('effectiveTo')}
              />
              <AdvancedSection>
                <Stack spacing={2}>
                  <TextField
                    error={Boolean(form.formState.errors.annualGrowthRate)}
                    helperText={form.formState.errors.annualGrowthRate?.message}
                    label="Annual growth % (optional)"
                    {...form.register('annualGrowthRate')}
                  />
                  <TextField
                    error={Boolean(form.formState.errors.salarySacrificeAmount)}
                    helperText={
                      form.formState.errors.salarySacrificeAmount?.message
                    }
                    label="Pre-tax contribution (optional)"
                    {...form.register('salarySacrificeAmount')}
                  />
                  <TextField
                    label="Notes (optional)"
                    multiline
                    {...form.register('notes')}
                  />
                </Stack>
              </AdvancedSection>
              {createIncome.error ? (
                <Alert severity="error">
                  {errorMessage(createIncome.error)}
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={
                createIncome.isPending ||
                incomeTypes.isPending ||
                Boolean(incomeTypes.error) ||
                !incomeTypes.data?.length
              }
              type="submit"
              variant="contained"
            >
              Add income source
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </Stack>
  );
}
