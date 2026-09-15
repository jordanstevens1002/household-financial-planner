import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Autocomplete,
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

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';
import { RepaymentOverridesPanel } from './RepaymentOverridesPanel';

type Loan = components['schemas']['LoanRead'];
type LoanGroup = components['schemas']['LoanGroupRead'];
type Lookup = components['schemas']['LookupRead'];
type Person = components['schemas']['PersonRead'];

function addMoneyAmounts(amounts: string[]): string {
  const cents = amounts.reduce((total, amount) => {
    const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(amount);
    if (!match)
      throw new TypeError('Money amount must have at most two decimals');
    return (
      total + BigInt(match[1]!) * 100n + BigInt((match[2] ?? '').padEnd(2, '0'))
    );
  }, 0n);
  const digits = cents.toString().padStart(3, '0');
  return `${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

function formatExactMoney(amount: string, currency: string): string {
  const [integer = '0', fraction = '00'] = amount.split('.');
  return `${currency} ${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`;
}

function totalsByCurrency(loans: Loan[]): Array<[string, string]> {
  const amounts = new Map<string, string[]>();
  loans.forEach((loan) => {
    amounts.set(loan.currency, [
      ...(amounts.get(loan.currency) ?? []),
      loan.opening_balance,
    ]);
  });
  return [...amounts.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([loanCurrency, values]) => [loanCurrency, addMoneyAmounts(values)]);
}

const loanSchema = z.object({
  accountReference: z
    .string()
    .trim()
    .max(50)
    .refine((value) => {
      if (!value) return true;
      const masks = [...value].filter((character) =>
        '*•xX'.includes(character),
      );
      const visible = value.replace(/[^a-zA-Z0-9]/g, '').replace(/^[xX]+/, '');
      return masks.length >= 3 && visible.length >= 2 && visible.length <= 4;
    }, 'Hide all but the final 2 to 4 characters, for example ****1234'),
  borrowerPersonIds: z.array(z.string()).max(20),
  displayName: z.string().trim().min(1, 'Enter a loan name').max(200),
  initialInterestRate: z
    .string()
    .refine(
      (value) =>
        value.trim() !== '' &&
        Number.isFinite(Number(value)) &&
        Number(value) >= 0 &&
        Number(value) <= 100,
      'Enter a rate from 0 to 100',
    ),
  interestCalculationMethod: z
    .enum(['', 'DAILY', 'MONTHLY'])
    .refine((value) => value !== '', 'Choose how interest is calculated'),
  isInterestOnly: z
    .enum(['', 'false', 'true'])
    .refine((value) => value !== '', 'Choose a repayment type'),
  lender: z.string().trim().max(200),
  loanGroupId: z.string(),
  loanTypeId: z.string().min(1, 'Choose a loan type'),
  notes: z.string().trim().max(2000),
  openingBalance: z
    .string()
    .refine(
      (value) =>
        value.trim() !== '' &&
        Number.isFinite(Number(value)) &&
        Number(value) >= 0,
      'Enter an opening balance of zero or more',
    ),
  openingBalanceDate: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter an opening balance date'),
  originalBalance: z
    .string()
    .refine(
      (value) =>
        value.trim() === '' ||
        (Number.isFinite(Number(value)) && Number(value) >= 0),
      'Enter an original balance of zero or more',
    ),
  repaymentFrequency: z
    .enum(['', 'WEEKLY', 'FORTNIGHTLY', 'MONTHLY'])
    .refine((value) => value !== '', 'Choose a repayment frequency'),
  scheduledRepayment: z
    .string()
    .refine(
      (value) =>
        value.trim() === '' ||
        (Number.isFinite(Number(value)) && Number(value) >= 0),
      'Enter a repayment of zero or more',
    ),
  termMonths: z
    .string()
    .refine(
      (value) =>
        value.trim() === '' ||
        (/^\d+$/.test(value) && Number(value) > 0 && Number(value) <= 1200),
      'Enter a term from 1 to 1200 months',
    ),
});

type LoanFields = z.input<typeof loanSchema>;
type ValidLoanFields = z.output<typeof loanSchema>;

const defaults: LoanFields = {
  accountReference: '',
  borrowerPersonIds: [],
  displayName: '',
  initialInterestRate: '',
  interestCalculationMethod: '',
  isInterestOnly: '',
  lender: '',
  loanGroupId: '',
  loanTypeId: '',
  notes: '',
  openingBalance: '',
  openingBalanceDate: '',
  originalBalance: '',
  repaymentFrequency: '',
  scheduledRepayment: '',
  termMonths: '',
};

function fieldsForLoan(loan: Loan): LoanFields {
  return {
    accountReference: loan.account_reference_masked ?? '',
    borrowerPersonIds: [],
    displayName: loan.display_name,
    initialInterestRate: loan.initial_interest_rate,
    interestCalculationMethod: loan.interest_calculation_method,
    isInterestOnly: loan.is_interest_only ? 'true' : 'false',
    lender: loan.lender ?? '',
    loanGroupId: loan.loan_group_id ?? '',
    loanTypeId: loan.loan_type_id,
    notes: loan.notes ?? '',
    openingBalance: loan.opening_balance,
    openingBalanceDate: loan.opening_balance_date,
    originalBalance: loan.original_balance ?? '',
    repaymentFrequency: loan.repayment_frequency,
    scheduledRepayment: loan.scheduled_repayment ?? '',
    termMonths: loan.term_months?.toString() ?? '',
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function LoansPanel({
  canAdminister,
  canEdit,
  currency,
  householdId,
  propertyId,
  recordedDebt,
  recordedDebtDate,
}: {
  canAdminister: boolean;
  canEdit: boolean;
  currency: string;
  householdId: string;
  propertyId: string;
  recordedDebt: string | null;
  recordedDebtDate: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingLoan, setEditingLoan] = useState<Loan | null>(null);
  const [closingLoan, setClosingLoan] = useState<Loan | null>(null);
  const [borrowerLoan, setBorrowerLoan] = useState<Loan | null>(null);
  const [replacementBorrowerIds, setReplacementBorrowerIds] = useState<
    string[]
  >([]);
  const [groupDialogOpen, setGroupDialogOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState<LoanGroup | null>(null);
  const [removingGroup, setRemovingGroup] = useState<LoanGroup | null>(null);
  const [groupName, setGroupName] = useState('');
  const [groupNameError, setGroupNameError] = useState('');
  const form = useForm<LoanFields, unknown, ValidLoanFields>({
    defaultValues: defaults,
    resolver: zodResolver(loanSchema),
  });
  const loanTypeId = useWatch({ control: form.control, name: 'loanTypeId' });
  const loanGroupId = useWatch({ control: form.control, name: 'loanGroupId' });
  const repaymentFrequency = useWatch({
    control: form.control,
    name: 'repaymentFrequency',
  });
  const interestMethod = useWatch({
    control: form.control,
    name: 'interestCalculationMethod',
  });
  const repaymentType = useWatch({
    control: form.control,
    name: 'isInterestOnly',
  });
  const borrowerPersonIds = useWatch({
    control: form.control,
    name: 'borrowerPersonIds',
  });
  const loans = useQuery({
    queryFn: () =>
      apiRequest<Loan[]>(`/api/v1/households/${householdId}/loans`),
    queryKey: ['household-loans', householdId],
    retry: false,
  });
  const loanTypes = useQuery({
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/loan_type'),
    queryKey: ['lookups', 'loan_type'],
    retry: false,
  });
  const loanGroups = useQuery({
    queryFn: () =>
      apiRequest<LoanGroup[]>(`/api/v1/households/${householdId}/loan-groups`),
    queryKey: ['loan-groups', householdId],
    retry: false,
  });
  const propertyLoans = (loans.data ?? []).filter(
    (loan) => loan.property_id === propertyId,
  );
  const propertyGroups = (loanGroups.data ?? []).filter(
    (group) => group.property_id === propertyId,
  );
  const needsPeople =
    (dialogOpen && editingLoan == null) ||
    borrowerLoan != null ||
    propertyLoans.some((loan) => (loan.borrower_person_ids ?? []).length > 0);
  const people = useQuery({
    enabled: needsPeople,
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const saveLoan = useMutation({
    mutationFn: (fields: ValidLoanFields) =>
      apiRequest<Loan>(
        editingLoan
          ? `/api/v1/loans/${editingLoan.id}`
          : `/api/v1/households/${householdId}/loans`,
        {
          body: JSON.stringify({
            account_reference_masked: fields.accountReference || null,
            display_name: fields.displayName.trim(),
            initial_interest_rate: fields.initialInterestRate,
            interest_calculation_method: fields.interestCalculationMethod,
            is_interest_only: fields.isInterestOnly === 'true',
            lender: fields.lender.trim() || null,
            loan_group_id: fields.loanGroupId || null,
            loan_type_id: fields.loanTypeId,
            notes: fields.notes.trim() || null,
            opening_balance: fields.openingBalance,
            opening_balance_date: fields.openingBalanceDate,
            original_balance: fields.originalBalance || null,
            repayment_frequency: fields.repaymentFrequency,
            scheduled_repayment: fields.scheduledRepayment || null,
            term_months: fields.termMonths ? Number(fields.termMonths) : null,
            ...(editingLoan
              ? {}
              : {
                  borrower_person_ids: fields.borrowerPersonIds,
                  currency,
                  is_active: true,
                  property_id: propertyId,
                }),
          }),
          csrfToken: auth.csrfToken(),
          method: editingLoan ? 'PATCH' : 'POST',
        },
      ),
    onError: (error) => notify(errorMessage(error), 'error'),
    onSuccess: async () => {
      setDialogOpen(false);
      form.reset(defaults);
      notify(editingLoan ? 'Loan corrected' : 'Loan added', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['property', propertyId] }),
        queryClient.invalidateQueries({
          queryKey: ['property-state', propertyId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
      ]);
    },
  });
  const replaceBorrowers = useMutation({
    mutationFn: ({ loan, personIds }: { loan: Loan; personIds: string[] }) =>
      apiRequest<Loan>(`/api/v1/loans/${loan.id}/borrowers`, {
        body: JSON.stringify({ borrower_person_ids: personIds }),
        csrfToken: auth.csrfToken(),
        method: 'PUT',
      }),
    onError: (error) => notify(errorMessage(error), 'error'),
    onSuccess: async (_, variables) => {
      setBorrowerLoan((current) =>
        current?.id === variables.loan.id ? null : current,
      );
      notify('Borrowers updated', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
      ]);
    },
  });
  const saveGroup = useMutation({
    mutationFn: (name: string) =>
      apiRequest<LoanGroup>(
        editingGroup
          ? `/api/v1/loan-groups/${editingGroup.id}`
          : `/api/v1/households/${householdId}/loan-groups`,
        {
          body: JSON.stringify(
            editingGroup
              ? { display_name: name }
              : { display_name: name, property_id: propertyId },
          ),
          csrfToken: auth.csrfToken(),
          method: editingGroup ? 'PATCH' : 'POST',
        },
      ),
    onError: (error) => notify(errorMessage(error), 'error'),
    onSuccess: async () => {
      setGroupDialogOpen(false);
      setEditingGroup(null);
      setGroupName('');
      notify(
        editingGroup ? 'Split group renamed' : 'Split group added',
        'success',
      );
      await queryClient.invalidateQueries({
        queryKey: ['loan-groups', householdId],
      });
    },
  });
  const removeGroup = useMutation({
    mutationFn: ({
      group,
      assignedLoanIds,
    }: {
      group: LoanGroup;
      assignedLoanIds: string[];
    }) => {
      const populated = assignedLoanIds.length > 0;
      return apiRequest<void>(
        `/api/v1/loan-groups/${group.id}${populated ? '/remove' : ''}`,
        {
          body: populated
            ? JSON.stringify({ assigned_loan_ids: assignedLoanIds })
            : undefined,
          csrfToken: auth.csrfToken(),
          method: populated ? 'POST' : 'DELETE',
        },
      );
    },
    onError: async (error) => {
      notify(errorMessage(error), 'error');
      if (error instanceof ApiError && error.status === 409) {
        setRemovingGroup(null);
        await Promise.all([
          queryClient.invalidateQueries({
            queryKey: ['loan-groups', householdId],
          }),
          queryClient.invalidateQueries({
            queryKey: ['household-loans', householdId],
          }),
        ]);
      }
    },
    onSuccess: async () => {
      setRemovingGroup(null);
      notify('Split group removed', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['loan-groups', householdId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
      ]);
    },
  });
  const closeLoan = useMutation({
    mutationFn: (loan: Loan) =>
      apiRequest<Loan>(`/api/v1/loans/${loan.id}/close`, {
        body: JSON.stringify({ effective_date: localCalendarDate() }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onError: (error) => notify(errorMessage(error), 'error'),
    onSuccess: async () => {
      setClosingLoan(null);
      notify('Loan closed', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
      ]);
    },
  });
  const openCreate = () => {
    setEditingLoan(null);
    form.reset(defaults);
    setDialogOpen(true);
  };
  const openCorrection = (loan: Loan) => {
    setEditingLoan(loan);
    form.reset(fieldsForLoan(loan));
    setDialogOpen(true);
  };
  const openBorrowers = (loan: Loan) => {
    setBorrowerLoan(loan);
    setReplacementBorrowerIds(loan.borrower_person_ids ?? []);
  };
  const personLabel = (person: Person) => {
    const today = localCalendarDate();
    const inactive =
      person.effective_from > today ||
      (person.effective_to != null && person.effective_to < today);
    return `${person.display_name}${inactive ? ' (inactive)' : ''}`;
  };
  const borrowerNames = (loan: Loan) => {
    const borrowerIds = loan.borrower_person_ids ?? [];
    if (borrowerIds.length === 0) return 'Not assigned';
    if (people.isPending) return 'Loading…';
    if (people.error) return 'Borrowers unavailable';
    return borrowerIds
      .map((personId) => {
        const person = people.data?.find((item) => item.id === personId);
        return person ? personLabel(person) : 'Unknown borrower';
      })
      .join(', ');
  };
  const openGroupDialog = (group: LoanGroup | null = null) => {
    setEditingGroup(group);
    setGroupName(group?.display_name ?? '');
    setGroupNameError('');
    setGroupDialogOpen(true);
  };
  const submitGroup = () => {
    const normalized = groupName.trim().replace(/\s+/g, ' ');
    if (!normalized) {
      setGroupNameError('Enter a split group name');
      return;
    }
    saveGroup.mutate(normalized);
  };
  const columns: DataColumn<Loan>[] = [
    { key: 'name', label: 'Loan', render: (loan) => loan.display_name },
    {
      key: 'type',
      label: 'Type',
      render: (loan) =>
        loanTypes.data?.find((item) => item.id === loan.loan_type_id)
          ?.display_name ?? 'Unavailable',
    },
    {
      key: 'balance',
      label: 'Opening balance',
      render: (loan) => formatCurrency(loan.opening_balance, loan.currency),
    },
    {
      key: 'date',
      label: 'Opening date',
      render: (loan) => formatDate(loan.opening_balance_date),
    },
    {
      key: 'rate',
      label: 'Interest rate',
      render: (loan) => `${loan.initial_interest_rate}%`,
    },
    {
      key: 'repayment',
      label: 'Scheduled repayment',
      render: (loan) =>
        loan.scheduled_repayment == null
          ? 'Not recorded'
          : `${formatCurrency(loan.scheduled_repayment, loan.currency)} ${loan.repayment_frequency.toLowerCase()}`,
    },
    {
      key: 'borrowers',
      label: 'Borrowers',
      render: borrowerNames,
    },
    {
      key: 'group',
      label: 'Split group',
      render: (loan) => {
        if (loan.loan_group_id == null) return 'Ungrouped';
        if (loanGroups.isPending) return 'Loading…';
        if (loanGroups.error) return 'Group unavailable';
        const group = loanGroups.data?.find(
          (item) => item.id === loan.loan_group_id,
        );
        return group?.property_id === propertyId
          ? group.display_name
          : 'Invalid group assignment';
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (loan) => (loan.is_active ? 'Active' : 'Closed'),
    },
    ...(canEdit
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (loan: Loan) => (
              <Stack direction="row" spacing={1}>
                <Button onClick={() => openCorrection(loan)}>Correct</Button>
                {loan.is_active ? (
                  <Button
                    disabled={replaceBorrowers.isPending}
                    onClick={() => openBorrowers(loan)}
                  >
                    Manage borrowers
                  </Button>
                ) : null}
                {loan.is_active ? (
                  <Button color="error" onClick={() => setClosingLoan(loan)}>
                    Close
                  </Button>
                ) : null}
              </Stack>
            ),
          },
        ]
      : []),
  ];
  const linkedOpeningTotals = totalsByCurrency(
    propertyLoans.filter((loan) => loan.is_active),
  );
  const linkedPropertyCurrencyBalance = linkedOpeningTotals.find(
    ([loanCurrency]) => loanCurrency === currency,
  )?.[1];
  const hasOtherCurrencies = linkedOpeningTotals.some(
    ([loanCurrency]) => loanCurrency !== currency,
  );
  const debtDiffers =
    recordedDebt == null ||
    linkedPropertyCurrencyBalance == null ||
    addMoneyAmounts([recordedDebt]) !==
      addMoneyAmounts([linkedPropertyCurrencyBalance]);
  const debtComparison =
    recordedDebt == null
      ? 'There is no dated property-debt record to compare with these loans.'
      : hasOtherCurrencies
        ? 'Loans in other currencies are shown separately and cannot be combined with recorded property debt.'
        : linkedPropertyCurrencyBalance == null
          ? `There is no linked ${currency} opening balance to compare.`
          : debtDiffers
            ? 'These figures differ.'
            : 'The figures currently match.';

  return (
    <Stack spacing={2}>
      <Stack
        direction="row"
        sx={{ alignItems: 'center', justifyContent: 'space-between' }}
      >
        <Typography variant="h2">Loans</Typography>
        {canEdit ? (
          <Stack direction="row" spacing={1}>
            <Button onClick={() => openGroupDialog()} variant="outlined">
              Add split group
            </Button>
            <Button onClick={openCreate} variant="outlined">
              Add loan
            </Button>
          </Stack>
        ) : null}
      </Stack>
      <Typography color="text.secondary">
        Record each loan separately. A property can have no loan, one loan or
        several loan splits.
      </Typography>
      {loanGroups.isPending ? (
        <CircularProgress aria-label="Loading loan split groups" size={24} />
      ) : loanGroups.error ? (
        <Alert
          action={
            <Button onClick={() => void loanGroups.refetch()}>Retry</Button>
          }
          severity="error"
        >
          Loan split groups could not be loaded.{' '}
          {errorMessage(loanGroups.error)}
        </Alert>
      ) : propertyGroups.length ? (
        <Stack aria-label="Loan split groups" spacing={1}>
          {propertyGroups.map((group) => {
            const groupedLoans = propertyLoans.filter(
              (loan) => loan.loan_group_id === group.id,
            );
            const totals = totalsByCurrency(groupedLoans);
            const formattedTotals = totals.length
              ? totals
                  .map(([loanCurrency, amount]) =>
                    formatExactMoney(amount, loanCurrency),
                  )
                  .join('; ')
              : 'none';
            return (
              <Alert
                action={
                  canEdit ? (
                    <Stack direction="row" spacing={1}>
                      <Button
                        aria-label={`Rename ${group.display_name}`}
                        onClick={() => openGroupDialog(group)}
                      >
                        Rename
                      </Button>
                      <Button
                        aria-label={`Remove ${group.display_name}`}
                        color="error"
                        disabled={groupedLoans.length > 0 && !canAdminister}
                        onClick={() => setRemovingGroup(group)}
                      >
                        Remove
                      </Button>
                    </Stack>
                  ) : undefined
                }
                key={group.id}
                severity="info"
              >
                <strong>{group.display_name}</strong>: {groupedLoans.length}{' '}
                {groupedLoans.length === 1 ? 'loan' : 'loans'}; derived opening
                {totals.length === 1 ? ' balance' : ' balances'}{' '}
                {formattedTotals}.
                {groupedLoans.length > 0 && canEdit && !canAdminister
                  ? ' A household administrator or owner can remove this group and move its loans to Ungrouped.'
                  : ''}
              </Alert>
            );
          })}
        </Stack>
      ) : null}
      {propertyLoans.length ? (
        <Alert severity={debtDiffers ? 'warning' : 'info'}>
          Recorded property debt as of {formatDate(recordedDebtDate)} is{' '}
          {recordedDebt == null
            ? 'not available'
            : formatCurrency(recordedDebt, currency)}
          . Active linked-loan opening balances total{' '}
          {linkedOpeningTotals.length
            ? linkedOpeningTotals
                .map(([loanCurrency, amount]) =>
                  formatExactMoney(amount, loanCurrency),
                )
                .join('; ')
            : 'none'}
          . {debtComparison} Opening balances do not yet replace the dated
          property-debt record; reconcile discrepancies before relying on both
          figures.
        </Alert>
      ) : null}
      {loans.isPending ? (
        <CircularProgress aria-label="Loading property loans" size={24} />
      ) : loans.error ? (
        <Alert
          action={<Button onClick={() => void loans.refetch()}>Retry</Button>}
          severity="error"
        >
          Property loans could not be loaded. {errorMessage(loans.error)}
        </Alert>
      ) : propertyLoans.length ? (
        <DataTable
          caption="Property loans"
          columns={columns}
          getRowKey={(loan) => loan.id}
          rows={propertyLoans}
        />
      ) : (
        <EmptyState
          description={
            canEdit
              ? 'Add a loan only when this property has one.'
              : 'No loans are recorded for this property.'
          }
          title="No property loans"
        />
      )}
      {propertyLoans.length ? (
        <RepaymentOverridesPanel
          canEdit={canEdit}
          householdId={householdId}
          loans={propertyLoans}
        />
      ) : null}

      <Dialog
        fullWidth
        maxWidth="md"
        onClose={() => setDialogOpen(false)}
        open={dialogOpen}
      >
        <Stack
          component="form"
          onSubmit={(event) =>
            void form.handleSubmit((fields) => saveLoan.mutate(fields))(event)
          }
        >
          <DialogTitle>
            {editingLoan ? 'Correct property loan' : 'Add a property loan'}
          </DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              {loanTypes.error ? (
                <Alert
                  action={
                    <Button onClick={() => void loanTypes.refetch()}>
                      Retry
                    </Button>
                  }
                  severity="error"
                >
                  Loan types could not be loaded.
                </Alert>
              ) : null}
              <TextField
                error={Boolean(form.formState.errors.displayName)}
                helperText={form.formState.errors.displayName?.message}
                label="Loan name"
                {...form.register('displayName')}
              />
              <TextField
                disabled={loanTypes.isPending || Boolean(loanTypes.error)}
                error={Boolean(form.formState.errors.loanTypeId)}
                helperText={form.formState.errors.loanTypeId?.message}
                label="Loan type"
                select
                value={loanTypeId ?? ''}
                {...form.register('loanTypeId')}
              >
                {(loanTypes.data ?? []).map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.display_name}
                  </MenuItem>
                ))}
              </TextField>
              {!editingLoan ? (
                people.error ? (
                  <Alert
                    action={
                      <Button onClick={() => void people.refetch()}>
                        Retry
                      </Button>
                    }
                    severity="warning"
                  >
                    People could not be loaded. You can save this loan without
                    named borrowers and add them later.
                  </Alert>
                ) : (
                  <Autocomplete
                    disableCloseOnSelect
                    disabled={people.isPending}
                    getOptionLabel={personLabel}
                    isOptionEqualToValue={(option, value) =>
                      option.id === value.id
                    }
                    multiple
                    onChange={(_, selected) =>
                      form.setValue(
                        'borrowerPersonIds',
                        selected.map((person) => person.id),
                        { shouldDirty: true },
                      )
                    }
                    options={people.data ?? []}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        helperText="Optional; repayments default equally across named borrowers."
                        label="Borrowers (optional)"
                      />
                    )}
                    value={(people.data ?? []).filter((person) =>
                      (borrowerPersonIds ?? []).includes(person.id),
                    )}
                  />
                )
              ) : null}
              <TextField
                disabled={loanGroups.isPending || Boolean(loanGroups.error)}
                helperText={
                  loanGroups.error
                    ? 'Groups are unavailable; retry from the Loans section.'
                    : 'Optional; each loan keeps its own balance and terms.'
                }
                label="Split group (optional)"
                select
                value={loanGroupId ?? ''}
                {...form.register('loanGroupId')}
              >
                <MenuItem value="">Ungrouped</MenuItem>
                {propertyGroups.map((group) => (
                  <MenuItem key={group.id} value={group.id}>
                    {group.display_name}
                  </MenuItem>
                ))}
              </TextField>
              <Stack direction="row" spacing={2}>
                <TextField
                  error={Boolean(form.formState.errors.openingBalance)}
                  fullWidth
                  helperText={form.formState.errors.openingBalance?.message}
                  label={`Opening balance (${currency})`}
                  {...form.register('openingBalance')}
                />
                <TextField
                  error={Boolean(form.formState.errors.openingBalanceDate)}
                  fullWidth
                  helperText={form.formState.errors.openingBalanceDate?.message}
                  label="Opening balance date"
                  slotProps={{ inputLabel: { shrink: true } }}
                  type="date"
                  {...form.register('openingBalanceDate')}
                />
                <TextField
                  error={Boolean(form.formState.errors.initialInterestRate)}
                  fullWidth
                  helperText={
                    form.formState.errors.initialInterestRate?.message
                  }
                  label="Annual interest rate %"
                  {...form.register('initialInterestRate')}
                />
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField
                  error={Boolean(form.formState.errors.scheduledRepayment)}
                  fullWidth
                  helperText={
                    form.formState.errors.scheduledRepayment?.message ??
                    'Optional'
                  }
                  label={`Scheduled repayment (${currency})`}
                  {...form.register('scheduledRepayment')}
                />
                <TextField
                  error={Boolean(form.formState.errors.repaymentFrequency)}
                  fullWidth
                  helperText={form.formState.errors.repaymentFrequency?.message}
                  label="Repayment frequency"
                  select
                  value={repaymentFrequency ?? ''}
                  {...form.register('repaymentFrequency')}
                >
                  <MenuItem value="WEEKLY">Weekly</MenuItem>
                  <MenuItem value="FORTNIGHTLY">Fortnightly</MenuItem>
                  <MenuItem value="MONTHLY">Monthly</MenuItem>
                </TextField>
                <TextField
                  error={Boolean(form.formState.errors.termMonths)}
                  fullWidth
                  helperText={
                    form.formState.errors.termMonths?.message ?? 'Optional'
                  }
                  label="Term in months"
                  {...form.register('termMonths')}
                />
              </Stack>
              <TextField
                error={Boolean(form.formState.errors.isInterestOnly)}
                helperText={form.formState.errors.isInterestOnly?.message}
                label="Repayment type"
                select
                value={repaymentType ?? ''}
                {...form.register('isInterestOnly')}
              >
                <MenuItem value="false">Principal and interest</MenuItem>
                <MenuItem value="true">Interest only</MenuItem>
              </TextField>
              <TextField
                error={Boolean(form.formState.errors.interestCalculationMethod)}
                helperText={
                  form.formState.errors.interestCalculationMethod?.message
                }
                label="Interest calculation"
                select
                value={interestMethod ?? ''}
                {...form.register('interestCalculationMethod')}
              >
                <MenuItem value="DAILY">Daily</MenuItem>
                <MenuItem value="MONTHLY">Monthly</MenuItem>
              </TextField>
              <AdvancedSection description="Lender details, original balance and notes are optional specialist records.">
                <Stack spacing={2}>
                  <TextField
                    label="Lender (optional)"
                    {...form.register('lender')}
                  />
                  <TextField
                    error={Boolean(form.formState.errors.accountReference)}
                    helperText={
                      form.formState.errors.accountReference?.message ??
                      'Use a masked value such as ****1234; never enter the complete number.'
                    }
                    label="Masked account reference (optional)"
                    {...form.register('accountReference')}
                  />
                  <TextField
                    error={Boolean(form.formState.errors.originalBalance)}
                    helperText={
                      form.formState.errors.originalBalance?.message ??
                      'Optional'
                    }
                    label={`Original balance (${currency}, optional)`}
                    {...form.register('originalBalance')}
                  />
                  <TextField
                    label="Notes (optional)"
                    multiline
                    minRows={2}
                    {...form.register('notes')}
                  />
                </Stack>
              </AdvancedSection>
              {saveLoan.error ? (
                <Alert severity="error">
                  The loan could not be saved. {errorMessage(saveLoan.error)}
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button
              disabled={
                saveLoan.isPending ||
                loanTypes.isPending ||
                Boolean(loanTypes.error)
              }
              type="submit"
              variant="contained"
            >
              {editingLoan ? 'Save correction' : 'Save loan'}
            </Button>
          </DialogActions>
        </Stack>
      </Dialog>
      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={() => {
          if (!replaceBorrowers.isPending) setBorrowerLoan(null);
        }}
        open={Boolean(borrowerLoan)}
      >
        <DialogTitle>
          Manage borrowers for {borrowerLoan?.display_name ?? 'loan'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography color="text.secondary">
              Scheduled repayments default equally across these people unless an
              Advanced dated override applies. Leaving this empty keeps the
              repayment at whole-household level.
            </Typography>
            <Alert severity="warning">
              Ordinary borrowers are undated defaults. Saving here changes
              repayment attribution from the loan opening date, including past
              cash-flow views. Use a dated Advanced repayment override when
              responsibility changes over time. Closed loans cannot be changed.
            </Alert>
            {people.error ? (
              <Alert
                action={
                  <Button onClick={() => void people.refetch()}>Retry</Button>
                }
                severity="error"
              >
                Household people could not be loaded.{' '}
                {errorMessage(people.error)}
              </Alert>
            ) : (
              <Autocomplete
                disableCloseOnSelect
                disabled={people.isPending}
                getOptionLabel={personLabel}
                isOptionEqualToValue={(option, value) => option.id === value.id}
                multiple
                onChange={(_, selected) =>
                  setReplacementBorrowerIds(selected.map((person) => person.id))
                }
                options={people.data ?? []}
                renderInput={(params) => (
                  <TextField {...params} label="Borrowers" />
                )}
                value={(people.data ?? []).filter((person) =>
                  replacementBorrowerIds.includes(person.id),
                )}
              />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            disabled={replaceBorrowers.isPending}
            onClick={() => setBorrowerLoan(null)}
          >
            Cancel
          </Button>
          <Button
            disabled={
              replaceBorrowers.isPending ||
              people.isPending ||
              Boolean(people.error)
            }
            onClick={() =>
              borrowerLoan &&
              replaceBorrowers.mutate({
                loan: borrowerLoan,
                personIds: replacementBorrowerIds,
              })
            }
            variant="contained"
          >
            Save borrowers
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={() => setGroupDialogOpen(false)}
        open={groupDialogOpen}
      >
        <DialogTitle>
          {editingGroup ? 'Rename split group' : 'Add a split group'}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            error={Boolean(groupNameError)}
            fullWidth
            helperText={
              groupNameError ||
              'Use a familiar name such as Fixed or Offset split.'
            }
            label="Split group name"
            onChange={(event) => {
              setGroupName(event.target.value);
              setGroupNameError('');
            }}
            sx={{ mt: 1 }}
            value={groupName}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGroupDialogOpen(false)}>Cancel</Button>
          <Button
            disabled={saveGroup.isPending}
            onClick={submitGroup}
            variant="contained"
          >
            {editingGroup ? 'Save name' : 'Add group'}
          </Button>
        </DialogActions>
      </Dialog>
      <ConfirmDialog
        confirmLabel="Close loan"
        description="Closing this loan keeps its record but removes its scheduled repayment from current household cash flow."
        onCancel={() => setClosingLoan(null)}
        onConfirm={() => closingLoan && closeLoan.mutate(closingLoan)}
        open={Boolean(closingLoan)}
        pending={closeLoan.isPending}
        title={`Close ${closingLoan?.display_name ?? 'loan'}?`}
      />
      <ConfirmDialog
        confirmLabel="Remove group"
        description={
          removingGroup &&
          propertyLoans.some((loan) => loan.loan_group_id === removingGroup.id)
            ? `Removing this group will move ${propertyLoans
                .filter((loan) => loan.loan_group_id === removingGroup.id)
                .map((loan) => loan.display_name)
                .join(', ')} to Ungrouped. No loan will be deleted.`
            : 'This removes the empty catalogue group. It does not delete or change any loan.'
        }
        onCancel={() => setRemovingGroup(null)}
        onConfirm={() =>
          removingGroup &&
          removeGroup.mutate({
            assignedLoanIds: propertyLoans
              .filter((loan) => loan.loan_group_id === removingGroup.id)
              .map((loan) => loan.id),
            group: removingGroup,
          })
        }
        open={Boolean(removingGroup)}
        pending={removeGroup.isPending}
        title={`Remove ${removingGroup?.display_name ?? 'split group'}?`}
      />
    </Stack>
  );
}
