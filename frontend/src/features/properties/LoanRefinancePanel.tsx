import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { z } from 'zod';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Loan = components['schemas']['LoanRead'];
type Lookup = components['schemas']['LookupRead'];
type RefinanceResult = components['schemas']['RefinanceRead'];

const moneyPattern = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const ratePattern = /^(?:\d{1,2}(?:\.\d{1,4})?|100(?:\.0{1,4})?)$/;
const refinanceSchema = z.object({
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
  displayName: z
    .string()
    .trim()
    .min(1, 'Enter a replacement loan name')
    .max(200),
  effectiveDate: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter the refinance date')
    .refine(
      (value) => value <= localCalendarDate(),
      'A completed refinance cannot be future-dated',
    ),
  initialInterestRate: z
    .string()
    .regex(ratePattern, 'Enter a rate from 0 to 100'),
  interestCalculationMethod: z.enum(['DAILY', 'MONTHLY']),
  isInterestOnly: z.enum(['false', 'true']),
  lender: z.string().trim().max(200),
  loanTypeId: z.string().min(1, 'Choose a loan type'),
  notes: z.string().trim().max(2000),
  openingBalance: z
    .string()
    .regex(moneyPattern, 'Enter a valid payout balance'),
  repaymentFrequency: z.enum(['WEEKLY', 'FORTNIGHTLY', 'MONTHLY']),
  scheduledRepayment: z
    .string()
    .refine(
      (value) => value === '' || moneyPattern.test(value),
      'Enter a valid repayment amount',
    ),
  sourceLoanId: z.string().min(1, 'Choose the refinanced loan'),
  termMonths: z
    .string()
    .refine(
      (value) =>
        value === '' ||
        (/^\d+$/.test(value) && Number(value) > 0 && Number(value) <= 1200),
      'Enter a term from 1 to 1200 months',
    ),
});

type Fields = z.input<typeof refinanceSchema>;
type ValidFields = z.output<typeof refinanceSchema>;

function fieldsForLoan(loan: Loan): Fields {
  return {
    accountReference: loan.account_reference_masked ?? '',
    displayName: `${loan.display_name} replacement`,
    effectiveDate: localCalendarDate(),
    initialInterestRate: loan.initial_interest_rate,
    interestCalculationMethod: loan.interest_calculation_method,
    isInterestOnly: loan.is_interest_only ? 'true' : 'false',
    lender: loan.lender ?? '',
    loanTypeId: loan.loan_type_id,
    notes: '',
    openingBalance: loan.opening_balance,
    repaymentFrequency: loan.repayment_frequency,
    scheduledRepayment: loan.scheduled_repayment ?? '',
    sourceLoanId: loan.id,
    termMonths: loan.term_months?.toString() ?? '',
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function LoanRefinancePanel({
  canEdit,
  householdId,
  loans,
  propertyId,
}: {
  canEdit: boolean;
  householdId: string;
  loans: Loan[];
  propertyId: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const activeLoans = loans.filter((loan) => loan.is_active);
  const [open, setOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<RefinanceResult | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const form = useForm<Fields, unknown, ValidFields>({
    defaultValues: activeLoans[0] ? fieldsForLoan(activeLoans[0]) : undefined,
    resolver: zodResolver(refinanceSchema),
  });
  const sourceLoanId = useWatch({
    control: form.control,
    name: 'sourceLoanId',
  });
  const sourceLoan = activeLoans.find((loan) => loan.id === sourceLoanId);
  const borrowerCount = sourceLoan?.borrower_person_ids?.length ?? 0;
  const loanTypes = useQuery({
    enabled: open,
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/loan_type'),
    queryKey: ['lookups', 'loan_type'],
    retry: false,
  });
  const availableLoanTypes =
    loanTypes.data ??
    (sourceLoan
      ? [
          {
            code: 'CURRENT',
            display_name: 'Current loan type',
            id: sourceLoan.loan_type_id,
            is_active: true,
          },
        ]
      : []);
  const refinance = useMutation({
    mutationFn: (fields: ValidFields) => {
      const loan = loans.find((item) => item.id === fields.sourceLoanId);
      if (!loan) throw new Error('The refinanced loan is no longer available');
      return apiRequest<RefinanceResult>(`/api/v1/loans/${loan.id}/refinance`, {
        body: JSON.stringify({
          effective_at: `${fields.effectiveDate}T00:00:00Z`,
          idempotency_key: idempotencyKey,
          notes: fields.notes.trim() || null,
          replacement_loan: {
            account_reference_masked: fields.accountReference || null,
            borrower_person_ids: loan.borrower_person_ids ?? [],
            currency: loan.currency,
            display_name: fields.displayName.trim(),
            initial_interest_rate: fields.initialInterestRate,
            interest_calculation_method: fields.interestCalculationMethod,
            is_active: true,
            is_interest_only: fields.isInterestOnly === 'true',
            lender: fields.lender.trim() || null,
            loan_group_id: loan.loan_group_id,
            loan_type_id: fields.loanTypeId,
            notes: fields.notes.trim() || null,
            opening_balance: fields.openingBalance,
            opening_balance_date: fields.effectiveDate,
            original_balance: fields.openingBalance,
            property_id: propertyId,
            repayment_frequency: fields.repaymentFrequency,
            scheduled_repayment: fields.scheduledRepayment || null,
            term_months: fields.termMonths ? Number(fields.termMonths) : null,
          },
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      });
    },
    onError: async (error) => {
      notify(errorMessage(error), 'error');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['property', propertyId] }),
        queryClient.invalidateQueries({
          queryKey: ['property-state', propertyId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['loan-schedule'] }),
        queryClient.invalidateQueries({
          queryKey: ['household-timeline', householdId],
        }),
      ]);
    },
    onSuccess: async (saved) => {
      setConfirmOpen(false);
      setResult(saved);
      notify('Refinance recorded', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['household-loans', householdId],
        }),
        queryClient.invalidateQueries({ queryKey: ['property', propertyId] }),
        queryClient.invalidateQueries({
          queryKey: ['property-state', propertyId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['loan-schedule'] }),
        queryClient.invalidateQueries({
          queryKey: ['household-timeline', householdId],
        }),
      ]);
    },
  });

  if (!canEdit || !activeLoans.length) return null;

  const openDialog = () => {
    form.reset(fieldsForLoan(activeLoans[0]!));
    setResult(null);
    setIdempotencyKey(crypto.randomUUID());
    setOpen(true);
  };
  const selectSource = (loanId: string) => {
    const loan = activeLoans.find((item) => item.id === loanId);
    if (loan) form.reset(fieldsForLoan(loan));
  };
  const reviewRefinance = (fields: ValidFields) => {
    const loan = activeLoans.find((item) => item.id === fields.sourceLoanId);
    if (loan && fields.effectiveDate < loan.opening_balance_date) {
      form.setError('effectiveDate', {
        message: 'The refinance date cannot predate the original loan',
      });
      return;
    }
    setConfirmOpen(true);
  };

  return (
    <>
      <Button onClick={openDialog} variant="outlined">
        Record refinance
      </Button>
      <Dialog
        fullWidth
        maxWidth="md"
        onClose={() => setOpen(false)}
        open={open}
      >
        <Stack
          component="form"
          onSubmit={(event) => void form.handleSubmit(reviewRefinance)(event)}
        >
          <DialogTitle>Record a completed refinance</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Alert severity="warning">
                This records an observed refinance: the old loan will be closed
                and a new active loan created. Use scenarios for changes you are
                only considering.
              </Alert>
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
                label="Loan being refinanced"
                onChange={(event) => selectSource(event.target.value)}
                select
                value={sourceLoanId ?? ''}
              >
                {activeLoans.map((loan) => (
                  <MenuItem key={loan.id} value={loan.id}>
                    {loan.display_name}
                  </MenuItem>
                ))}
              </TextField>
              {sourceLoan ? (
                <Alert severity="info">
                  Property, split group, currency and {borrowerCount}{' '}
                  {borrowerCount === 1 ? 'borrower' : 'borrowers'} will be
                  carried forward.
                </Alert>
              ) : null}
              <Stack direction="row" spacing={2}>
                <TextField
                  fullWidth
                  label="Refinance date"
                  slotProps={{ inputLabel: { shrink: true } }}
                  type="date"
                  {...form.register('effectiveDate')}
                  error={Boolean(form.formState.errors.effectiveDate)}
                  helperText={form.formState.errors.effectiveDate?.message}
                />
                <TextField
                  fullWidth
                  label="Replacement loan name"
                  {...form.register('displayName')}
                  error={Boolean(form.formState.errors.displayName)}
                  helperText={form.formState.errors.displayName?.message}
                />
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField
                  fullWidth
                  label="New lender (optional)"
                  {...form.register('lender')}
                />
                <TextField
                  fullWidth
                  label="Loan type"
                  select
                  disabled={loanTypes.isPending || Boolean(loanTypes.error)}
                  defaultValue={sourceLoan?.loan_type_id ?? ''}
                  {...form.register('loanTypeId')}
                >
                  {availableLoanTypes.map((type) => (
                    <MenuItem key={type.id} value={type.id}>
                      {type.display_name}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField
                  fullWidth
                  label={`Payout or opening balance (${sourceLoan?.currency ?? ''})`}
                  {...form.register('openingBalance')}
                  error={Boolean(form.formState.errors.openingBalance)}
                  helperText={form.formState.errors.openingBalance?.message}
                />
                <TextField
                  fullWidth
                  label="Annual interest rate %"
                  {...form.register('initialInterestRate')}
                  error={Boolean(form.formState.errors.initialInterestRate)}
                  helperText={
                    form.formState.errors.initialInterestRate?.message
                  }
                />
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField
                  fullWidth
                  label="Scheduled repayment"
                  {...form.register('scheduledRepayment')}
                  error={Boolean(form.formState.errors.scheduledRepayment)}
                  helperText={form.formState.errors.scheduledRepayment?.message}
                />
                <TextField
                  fullWidth
                  label="Term (months)"
                  {...form.register('termMonths')}
                  error={Boolean(form.formState.errors.termMonths)}
                  helperText={form.formState.errors.termMonths?.message}
                />
                <TextField
                  fullWidth
                  label="Frequency"
                  select
                  defaultValue={sourceLoan?.repayment_frequency}
                  {...form.register('repaymentFrequency')}
                >
                  <MenuItem value="WEEKLY">Weekly</MenuItem>
                  <MenuItem value="FORTNIGHTLY">Fortnightly</MenuItem>
                  <MenuItem value="MONTHLY">Monthly</MenuItem>
                </TextField>
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField
                  fullWidth
                  label="Repayment type"
                  select
                  defaultValue={sourceLoan?.is_interest_only ? 'true' : 'false'}
                  {...form.register('isInterestOnly')}
                >
                  <MenuItem value="false">Principal and interest</MenuItem>
                  <MenuItem value="true">Interest only</MenuItem>
                </TextField>
                <TextField
                  fullWidth
                  label="Interest calculation"
                  select
                  defaultValue={sourceLoan?.interest_calculation_method}
                  {...form.register('interestCalculationMethod')}
                >
                  <MenuItem value="DAILY">Daily</MenuItem>
                  <MenuItem value="MONTHLY">Monthly</MenuItem>
                </TextField>
              </Stack>
              <TextField
                label="Masked account reference (optional)"
                {...form.register('accountReference')}
                error={Boolean(form.formState.errors.accountReference)}
                helperText={form.formState.errors.accountReference?.message}
              />
              <TextField
                label="Notes (optional)"
                multiline
                minRows={2}
                {...form.register('notes')}
              />
              {refinance.error ? (
                <Alert severity="error">
                  The refinance could not be recorded.{' '}
                  {errorMessage(refinance.error)}
                </Alert>
              ) : null}
              {result ? (
                <Alert severity="success">
                  {result.replacement_loan.display_name} was created with an
                  opening balance of{' '}
                  {formatCurrency(
                    result.replacement_loan.opening_balance,
                    result.replacement_loan.currency,
                  )}{' '}
                  on {formatDate(result.replacement_loan.opening_balance_date)}.
                  The prior loan is closed.
                </Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button
              disabled={refinance.isPending}
              onClick={() => setOpen(false)}
            >
              Close
            </Button>
            <Button
              disabled={
                refinance.isPending ||
                Boolean(result) ||
                Boolean(loanTypes.error)
              }
              type="submit"
              variant="contained"
            >
              Review refinance
            </Button>
          </DialogActions>
        </Stack>
      </Dialog>
      <ConfirmDialog
        confirmLabel="Record refinance"
        description={`Close ${sourceLoan?.display_name ?? 'the old loan'} and create the replacement as an observed financial record? This cannot be treated as a proposal later.`}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() =>
          void form.handleSubmit((fields) => refinance.mutate(fields))()
        }
        open={confirmOpen}
        pending={refinance.isPending}
        title="Confirm completed refinance"
      />
    </>
  );
}
