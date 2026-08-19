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
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';

type Loan = components['schemas']['LoanRead'];
type Lookup = components['schemas']['LookupRead'];

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
  displayName: '',
  initialInterestRate: '',
  interestCalculationMethod: '',
  isInterestOnly: '',
  lender: '',
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
    displayName: loan.display_name,
    initialInterestRate: loan.initial_interest_rate,
    interestCalculationMethod: loan.interest_calculation_method,
    isInterestOnly: loan.is_interest_only ? 'true' : 'false',
    lender: loan.lender ?? '',
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
  canEdit,
  currency,
  householdId,
  propertyId,
  recordedDebt,
  recordedDebtDate,
}: {
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
  const form = useForm<LoanFields, unknown, ValidLoanFields>({
    defaultValues: defaults,
    resolver: zodResolver(loanSchema),
  });
  const loanTypeId = useWatch({ control: form.control, name: 'loanTypeId' });
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
  const propertyLoans = (loans.data ?? []).filter(
    (loan) => loan.property_id === propertyId,
  );
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
                  currency,
                  is_active: true,
                  loan_group_id: null,
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
  const closeLoan = useMutation({
    mutationFn: (loan: Loan) =>
      apiRequest<Loan>(`/api/v1/loans/${loan.id}`, {
        body: JSON.stringify({ is_active: false }),
        csrfToken: auth.csrfToken(),
        method: 'PATCH',
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
  const linkedOpeningBalance = propertyLoans
    .filter((loan) => loan.is_active)
    .reduce((total, loan) => total + Number(loan.opening_balance), 0);
  const debtDiffers =
    recordedDebt == null ||
    Math.abs(Number(recordedDebt) - linkedOpeningBalance) >= 0.01;
  const debtComparison =
    recordedDebt == null
      ? 'There is no dated property-debt record to compare with these loans.'
      : debtDiffers
        ? `These figures differ by ${formatCurrency(
            Math.abs(Number(recordedDebt) - linkedOpeningBalance),
            currency,
          )}.`
        : 'The figures currently match.';

  return (
    <Stack spacing={2}>
      <Stack
        direction="row"
        sx={{ alignItems: 'center', justifyContent: 'space-between' }}
      >
        <Typography variant="h2">Loans</Typography>
        {canEdit ? (
          <Button onClick={openCreate} variant="outlined">
            Add loan
          </Button>
        ) : null}
      </Stack>
      <Typography color="text.secondary">
        Record each loan separately. A property can have no loan, one loan or
        several loan splits.
      </Typography>
      {propertyLoans.length ? (
        <Alert severity={debtDiffers ? 'warning' : 'info'}>
          Recorded property debt as of {formatDate(recordedDebtDate)} is{' '}
          {recordedDebt == null
            ? 'not available'
            : formatCurrency(recordedDebt, currency)}
          . Active linked-loan opening balances total{' '}
          {formatCurrency(linkedOpeningBalance, currency)}. {debtComparison}{' '}
          Opening balances do not yet replace the dated property-debt record;
          reconcile discrepancies before relying on both figures.
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
      <ConfirmDialog
        confirmLabel="Close loan"
        description="Closing this loan keeps its record but removes its scheduled repayment from current household cash flow."
        onCancel={() => setClosingLoan(null)}
        onConfirm={() => closingLoan && closeLoan.mutate(closingLoan)}
        open={Boolean(closingLoan)}
        pending={closeLoan.isPending}
        title={`Close ${closingLoan?.display_name ?? 'loan'}?`}
      />
    </Stack>
  );
}
