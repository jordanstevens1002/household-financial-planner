import {
  Alert,
  Autocomplete,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

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

type Access = components['schemas']['HouseholdAccessRead'];
type Account = components['schemas']['RetirementAccountRead'];
type Currency = components['schemas']['CurrencyRead'];
type Lookup = components['schemas']['LookupRead'];
type Person = components['schemas']['PersonRead'];
type Provider = components['schemas']['RetirementProviderRead'];

const money = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed';

interface Draft {
  annualFees: string;
  accountTypeId: string;
  currency: string;
  displayName: string;
  expectedReturnRate: string;
  notes: string;
  openingBalance: string;
  openingBalanceDate: string;
  personId: string;
  providerCode: string;
  providerSettings: string;
  retirementAge: string;
}

const blank = (currency: string): Draft => ({
  accountTypeId: '',
  annualFees: '0',
  currency,
  displayName: '',
  expectedReturnRate: '0',
  notes: '',
  openingBalance: '0',
  openingBalanceDate: localCalendarDate(),
  personId: '',
  providerCode: '',
  providerSettings: '{}',
  retirementAge: '',
});

function AccountDialog({
  accountTypes,
  currencies,
  householdId,
  householdCurrency,
  onClose,
  people,
  providers,
}: {
  accountTypes: Lookup[];
  currencies: Currency[];
  householdId: string;
  householdCurrency: string;
  onClose: () => void;
  people: Person[];
  providers: Provider[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [draft, setDraft] = useState(() => blank(householdCurrency));
  const [validation, setValidation] = useState('');
  const field =
    (key: keyof Draft) => (event: React.ChangeEvent<HTMLInputElement>) =>
      setDraft((current) => ({ ...current, [key]: event.target.value }));
  const create = useMutation({
    mutationFn: (body: components['schemas']['RetirementAccountCreate']) =>
      apiRequest<Account>(
        `/api/v1/households/${householdId}/retirement-accounts`,
        {
          body: JSON.stringify(body),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['retirement-accounts', householdId],
      });
      notification.notify('Retirement account saved.', 'success');
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    if (!draft.displayName.trim() || !draft.accountTypeId)
      return setValidation('Name and account type are required.');
    if (!money.test(draft.openingBalance) || !money.test(draft.annualFees))
      return setValidation(
        'Balances and fees require non-negative amounts with at most two decimals.',
      );
    if (
      !/^-?(?:100(?:\.0{1,4})?|\d{1,2}(?:\.\d{1,4})?)$/.test(
        draft.expectedReturnRate,
      )
    )
      return setValidation(
        'Expected return must be between -100 and 100 with at most four decimals.',
      );
    if (
      draft.retirementAge &&
      (!/^\d{1,3}$/.test(draft.retirementAge) ||
        Number(draft.retirementAge) > 120)
    )
      return setValidation(
        'Retirement age must be a whole number from 0 to 120.',
      );
    let settings: Record<string, unknown>;
    try {
      const parsed = JSON.parse(draft.providerSettings) as unknown;
      if (
        typeof parsed !== 'object' ||
        parsed === null ||
        Array.isArray(parsed)
      )
        throw new Error();
      settings = parsed as Record<string, unknown>;
    } catch {
      return setValidation('Provider settings must be a valid JSON object.');
    }
    create.mutate({
      account_type_id: draft.accountTypeId,
      annual_fees: draft.annualFees,
      currency: draft.currency,
      display_name: draft.displayName.trim(),
      expected_return_rate: draft.expectedReturnRate,
      is_active: true,
      notes: draft.notes.trim() || null,
      opening_balance: draft.openingBalance,
      opening_balance_date: draft.openingBalanceDate,
      person_id: draft.personId || null,
      provider_code: draft.providerCode || null,
      provider_settings: draft.providerCode ? settings : {},
      retirement_age: draft.retirementAge ? Number(draft.retirementAge) : null,
    });
  };
  return (
    <Dialog
      fullWidth
      maxWidth="md"
      onClose={create.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Add retirement account</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField
            label="Account name"
            onChange={field('displayName')}
            value={draft.displayName}
          />
          <TextField
            label="Account type"
            onChange={field('accountTypeId')}
            select
            value={draft.accountTypeId}
          >
            {accountTypes.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            helperText="Optional — leave blank for a household-level account"
            label="Person"
            onChange={field('personId')}
            select
            value={draft.personId}
          >
            <MenuItem value="">Whole household</MenuItem>
            {people.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <Autocomplete
            getOptionLabel={(item) => `${item.code} — ${item.display_name}`}
            onChange={(_, item) =>
              setDraft((current) => ({
                ...current,
                currency: item?.code ?? '',
              }))
            }
            options={currencies}
            renderInput={(params) => <TextField {...params} label="Currency" />}
            value={
              currencies.find((item) => item.code === draft.currency) ?? null
            }
          />
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Opening balance"
              onChange={field('openingBalance')}
              value={draft.openingBalance}
            />
            <TextField
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
              label="Opening balance date"
              onChange={field('openingBalanceDate')}
              type="date"
              value={draft.openingBalanceDate}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Expected annual return (%)"
              onChange={field('expectedReturnRate')}
              value={draft.expectedReturnRate}
            />
            <TextField
              fullWidth
              label="Annual fees"
              onChange={field('annualFees')}
              value={draft.annualFees}
            />
            <TextField
              fullWidth
              label="Planned retirement age (optional)"
              onChange={field('retirementAge')}
              value={draft.retirementAge}
            />
          </Stack>
          <TextField
            label="Installed provider (optional)"
            onChange={field('providerCode')}
            select
            value={draft.providerCode}
          >
            <MenuItem value="">No provider</MenuItem>
            {providers.map((item) => (
              <MenuItem key={item.code} value={item.code}>
                {item.display_name}
              </MenuItem>
            ))}
          </TextField>
          <AdvancedSection description="Provider-specific settings and personal notes are optional.">
            <Stack spacing={2}>
              <TextField
                label="Provider settings (JSON)"
                minRows={3}
                multiline
                onChange={field('providerSettings')}
                value={draft.providerSettings}
              />
              <TextField
                label="Notes"
                minRows={2}
                multiline
                onChange={field('notes')}
                value={draft.notes}
              />
            </Stack>
          </AdvancedSection>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {create.error ? (
            <Alert severity="error">
              Account could not be saved. {message(create.error)}
            </Alert>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={create.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={create.isPending}
          onClick={submit}
          variant="contained"
        >
          Save account
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function RetirementPage() {
  const household = useHousehold();
  const [open, setOpen] = useState(false);
  const id = household.selected?.id;
  const accounts = useQuery({
    enabled: !!id,
    queryFn: () =>
      apiRequest<Account[]>(`/api/v1/households/${id}/retirement-accounts`),
    queryKey: ['retirement-accounts', id],
    retry: false,
  });
  const access = useQuery({
    enabled: !!id,
    queryFn: () => apiRequest<Access>(`/api/v1/households/${id}/access`),
    queryKey: ['household-access', id],
    retry: false,
  });
  const people = useQuery({
    enabled: !!id,
    queryFn: () => apiRequest<Person[]>(`/api/v1/households/${id}/people`),
    queryKey: ['people', id],
    retry: false,
  });
  const types = useQuery({
    enabled: !!id,
    queryFn: () =>
      apiRequest<Lookup[]>('/api/v1/lookups/retirement_account_type'),
    queryKey: ['lookups', 'retirement_account_type'],
    retry: false,
  });
  const providers = useQuery({
    enabled: !!id,
    queryFn: () => apiRequest<Provider[]>('/api/v1/retirement-providers'),
    queryKey: ['retirement-providers'],
    retry: false,
  });
  const currencies = useQuery({
    enabled: open,
    queryFn: () => apiRequest<Currency[]>('/api/v1/reference/currencies'),
    queryKey: ['reference', 'currencies'],
    retry: false,
  });
  if (!household.selected)
    return (
      <EmptyState
        title="Choose a household"
        description="Select a household before reviewing retirement accounts."
      />
    );
  const failed =
    accounts.error ??
    access.error ??
    people.error ??
    types.error ??
    providers.error;
  if (
    accounts.isPending ||
    access.isPending ||
    people.isPending ||
    types.isPending ||
    providers.isPending
  )
    return <CircularProgress aria-label="Loading retirement accounts" />;
  if (failed)
    return (
      <Alert severity="error">
        Retirement accounts could not be loaded. {message(failed)}
      </Alert>
    );
  const accountRows = accounts.data ?? [];
  const accessValue = access.data!;
  const peopleRows = people.data ?? [];
  const providerRows = providers.data ?? [];
  const typeRows = types.data ?? [];
  const names = new Map(peopleRows.map((item) => [item.id, item.display_name]));
  const typeNames = new Map(
    typeRows.map((item) => [item.id, item.display_name]),
  );
  const columns: DataColumn<Account>[] = [
    { key: 'name', label: 'Account', render: (item) => item.display_name },
    {
      key: 'person',
      label: 'For',
      render: (item) =>
        item.person_id
          ? (names.get(item.person_id) ?? 'Unavailable person')
          : 'Whole household',
    },
    {
      key: 'type',
      label: 'Type',
      render: (item) => typeNames.get(item.account_type_id) ?? 'Unavailable',
    },
    {
      key: 'balance',
      label: 'Opening balance',
      render: (item) => formatCurrency(item.opening_balance, item.currency),
    },
    {
      key: 'date',
      label: 'Recorded',
      render: (item) => formatDate(item.opening_balance_date),
    },
    {
      key: 'return',
      label: 'Expected return',
      render: (item) => `${item.expected_return_rate}%`,
    },
    {
      key: 'status',
      label: 'Status',
      render: (item) => (item.is_active ? 'Active' : 'Inactive'),
    },
  ];
  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Retirement
        </Typography>
        <Typography color="text.secondary">
          Track long-term savings accounts without assuming a particular country
          or provider.
        </Typography>
      </Box>
      <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
        <Typography component="h2" variant="h6">
          Accounts
        </Typography>
        {accessValue.can_edit ? (
          <Button onClick={() => setOpen(true)} variant="contained">
            Add account
          </Button>
        ) : null}
      </Stack>
      {accountRows.length ? (
        <DataTable
          caption="Retirement accounts"
          columns={columns}
          getRowKey={(item) => item.id}
          rows={accountRows}
        />
      ) : (
        <EmptyState
          title="No retirement accounts"
          description={
            accessValue.can_edit
              ? 'Add an account to record its current position.'
              : 'No accounts have been recorded for this household.'
          }
        />
      )}
      {!accessValue.can_edit ? (
        <Alert severity="info">
          You have view-only access to this household.
        </Alert>
      ) : null}
      {open ? (
        currencies.isPending ? (
          <CircularProgress aria-label="Loading account form" />
        ) : currencies.error ? (
          <Alert severity="error">
            Currencies could not be loaded. Close the form and try again.
          </Alert>
        ) : (
          <AccountDialog
            accountTypes={typeRows}
            currencies={currencies.data}
            householdCurrency={household.selected.currency}
            householdId={household.selected.id}
            onClose={() => setOpen(false)}
            people={peopleRows.filter((item) => item.is_active)}
            providers={providerRows}
          />
        )
      ) : null}
    </Stack>
  );
}
