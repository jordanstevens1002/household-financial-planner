import {
  Alert,
  Button,
  Chip,
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
import { useMemo, useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Goal = components['schemas']['GoalRead'];
type Loan = components['schemas']['LoanRead'];
type Lookup = components['schemas']['LookupRead'];
type TargetResult = components['schemas']['TargetCalculationRead'];

const moneyPattern = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function LoanTargetsPanel({
  canEdit,
  householdId,
  loans,
}: {
  canEdit: boolean;
  householdId: string;
  loans: Loan[];
}) {
  const auth = useAuth();
  const { notify } = useNotification();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [loanId, setLoanId] = useState(loans[0]?.id ?? '');
  const [displayName, setDisplayName] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [goalId, setGoalId] = useState('');
  const [asOf, setAsOf] = useState(localCalendarDate());
  const [result, setResult] = useState<TargetResult | null>(null);

  const goals = useQuery({
    enabled: open,
    queryFn: () =>
      apiRequest<Goal[]>(`/api/v1/households/${householdId}/goals`),
    queryKey: ['household-goals', householdId],
    retry: false,
  });
  const goalTypes = useQuery({
    enabled: open,
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/goal_type'),
    queryKey: ['lookups', 'goal_type'],
    retry: false,
  });
  const weeklyGoalType = goalTypes.data?.find(
    (item) => item.code === 'MAXIMUM_WEEKLY_REPAYMENT',
  );
  const loanGoals = useMemo(
    () =>
      (goals.data ?? []).filter(
        (goal) =>
          goal.loan_id && loans.some((loan) => loan.id === goal.loan_id),
      ),
    [goals.data, loans],
  );
  const selectedGoal = loanGoals.find((goal) => goal.id === goalId);
  const selectedLoan = loans.find((loan) => loan.id === selectedGoal?.loan_id);
  const creationLoan = loans.find((loan) => loan.id === loanId);
  const amountValid = moneyPattern.test(targetAmount.trim());

  const createGoal = useMutation({
    mutationFn: () => {
      if (!weeklyGoalType)
        throw new Error('Weekly repayment goal type is unavailable');
      return apiRequest<Goal>(`/api/v1/households/${householdId}/goals`, {
        body: JSON.stringify({
          display_name: displayName.trim(),
          goal_type_id: weeklyGoalType.id,
          is_active: true,
          loan_id: loanId,
          notes: notes.trim() || null,
          priority: 0,
          target_amount: targetAmount.trim(),
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      });
    },
    onError: (error) => notify(errorMessage(error), 'error'),
    onSuccess: async (goal) => {
      setCreateOpen(false);
      setDisplayName('');
      setTargetAmount('');
      setNotes('');
      setGoalId(goal.id);
      setResult(null);
      notify('Loan target added', 'success');
      await queryClient.invalidateQueries({
        queryKey: ['household-goals', householdId],
      });
    },
  });
  const calculate = useMutation({
    mutationFn: () => {
      if (!selectedGoal?.loan_id) throw new Error('Choose a loan target');
      return apiRequest<TargetResult>(
        `/api/v1/loans/${selectedGoal.loan_id}/target-calculation`,
        {
          body: JSON.stringify({ as_of: asOf, goal_id: selectedGoal.id }),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      );
    },
    onError: () => setResult(null),
    onSuccess: setResult,
  });

  const columns: DataColumn<Goal>[] = [
    { key: 'name', label: 'Target', render: (goal) => goal.display_name },
    {
      key: 'loan',
      label: 'Loan',
      render: (goal) =>
        loans.find((loan) => loan.id === goal.loan_id)?.display_name ??
        'Unavailable',
    },
    {
      key: 'amount',
      label: 'Maximum weekly repayment',
      render: (goal) => {
        const loan = loans.find((item) => item.id === goal.loan_id);
        return goal.target_amount && loan
          ? formatCurrency(goal.target_amount, loan.currency)
          : 'Unavailable';
      },
    },
    { key: 'priority', label: 'Priority', render: (goal) => goal.priority },
    {
      key: 'status',
      label: 'Status',
      render: (goal) => (goal.is_active ? 'Active' : 'Inactive'),
    },
  ];

  const closePanel = () => {
    if (!createGoal.isPending && !calculate.isPending) setOpen(false);
  };

  return (
    <>
      <Button
        onClick={() => {
          setOpen(true);
          setResult(null);
        }}
        variant="outlined"
      >
        Loan targets
      </Button>
      <Dialog fullWidth maxWidth="lg" onClose={closePanel} open={open}>
        <DialogTitle>Loan targets and repayment comfort</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              Targets are household planning preferences, not lender
              recommendations. Calculations use the loan balance, rate,
              remaining term and dated events recorded in the API.
            </Alert>
            {goals.isPending || goalTypes.isPending ? (
              <CircularProgress aria-label="Loading loan targets" size={24} />
            ) : goals.error || goalTypes.error ? (
              <Alert
                action={
                  <Button
                    onClick={() => {
                      void goals.refetch();
                      void goalTypes.refetch();
                    }}
                  >
                    Retry
                  </Button>
                }
                severity="error"
              >
                Loan targets could not be loaded.{' '}
                {errorMessage(goals.error ?? goalTypes.error)}
              </Alert>
            ) : (
              <>
                <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
                  <Typography variant="h3">Saved targets</Typography>
                  {canEdit ? (
                    <Button
                      disabled={!weeklyGoalType}
                      onClick={() => setCreateOpen(true)}
                    >
                      Add target
                    </Button>
                  ) : null}
                </Stack>
                {weeklyGoalType ? null : (
                  <Alert severity="warning">
                    The maximum weekly repayment goal type is not installed.
                  </Alert>
                )}
                {loanGoals.length ? (
                  <DataTable
                    caption="Household loan targets"
                    columns={columns}
                    getRowKey={(goal) => goal.id}
                    rows={loanGoals}
                  />
                ) : (
                  <EmptyState
                    description={
                      canEdit
                        ? 'Add a maximum weekly repayment that feels comfortable for this household.'
                        : 'No loan targets have been recorded.'
                    }
                    title="No loan targets"
                  />
                )}
                {loanGoals.length ? (
                  <Stack spacing={2}>
                    <Typography variant="h3">Calculate a target</Typography>
                    <Stack direction="row" spacing={2}>
                      <TextField
                        fullWidth
                        label="Saved target"
                        onChange={(event) => {
                          setGoalId(event.target.value);
                          setResult(null);
                        }}
                        select
                        value={goalId}
                      >
                        {loanGoals.map((goal) => (
                          <MenuItem key={goal.id} value={goal.id}>
                            {goal.display_name}
                          </MenuItem>
                        ))}
                      </TextField>
                      <TextField
                        fullWidth
                        label="Position date"
                        onChange={(event) => {
                          setAsOf(event.target.value);
                          setResult(null);
                        }}
                        slotProps={{ inputLabel: { shrink: true } }}
                        type="date"
                        value={asOf}
                      />
                      <Button
                        disabled={!goalId || !asOf || calculate.isPending}
                        onClick={() => calculate.mutate()}
                        variant="contained"
                      >
                        Calculate
                      </Button>
                    </Stack>
                    {calculate.error ? (
                      <Alert severity="error">
                        The target could not be calculated.{' '}
                        {errorMessage(calculate.error)}
                      </Alert>
                    ) : null}
                    {result && selectedLoan ? (
                      <Alert
                        severity={result.within_target ? 'success' : 'warning'}
                      >
                        <Stack spacing={1}>
                          <Stack direction="row" spacing={1}>
                            <Chip
                              color={
                                result.within_target ? 'success' : 'warning'
                              }
                              label={
                                result.within_target
                                  ? 'Within your target'
                                  : 'Above your target'
                              }
                              size="small"
                            />
                            <Typography>
                              Required{' '}
                              {result.repayment_frequency.toLowerCase()}{' '}
                              repayment:{' '}
                              {formatCurrency(
                                result.required_repayment,
                                selectedLoan.currency,
                              )}
                            </Typography>
                          </Stack>
                          <Typography>
                            Maximum weekly target:{' '}
                            {formatCurrency(
                              result.target_amount,
                              selectedLoan.currency,
                            )}
                            . Estimated payoff:{' '}
                            {result.estimated_payoff_date
                              ? formatDate(result.estimated_payoff_date)
                              : 'not reached in the recorded term'}
                            .
                          </Typography>
                        </Stack>
                      </Alert>
                    ) : null}
                  </Stack>
                ) : null}
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closePanel}>Close</Button>
        </DialogActions>
      </Dialog>

      <Dialog
        fullWidth
        maxWidth="sm"
        onClose={() => {
          if (!createGoal.isPending) setCreateOpen(false);
        }}
        open={createOpen}
      >
        <DialogTitle>Add a loan target</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Target name"
              onChange={(event) => setDisplayName(event.target.value)}
              value={displayName}
            />
            <TextField
              label="Loan"
              onChange={(event) => setLoanId(event.target.value)}
              select
              value={loanId}
            >
              {loans.map((loan) => (
                <MenuItem key={loan.id} value={loan.id}>
                  {loan.display_name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              error={targetAmount !== '' && !amountValid}
              helperText={
                creationLoan
                  ? `Enter a weekly amount in ${creationLoan.currency}.`
                  : 'Choose a loan.'
              }
              label="Maximum comfortable weekly repayment"
              onChange={(event) => setTargetAmount(event.target.value)}
              value={targetAmount}
            />
            <TextField
              error={notes.length > 2000}
              helperText="Optional"
              label="Notes"
              multiline
              minRows={2}
              onChange={(event) => setNotes(event.target.value)}
              value={notes}
            />
            {createGoal.error ? (
              <Alert severity="error">
                The target could not be saved. {errorMessage(createGoal.error)}
              </Alert>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button
            disabled={
              createGoal.isPending ||
              !displayName.trim() ||
              displayName.trim().length > 200 ||
              !loanId ||
              !amountValid ||
              notes.length > 2000 ||
              !weeklyGoalType
            }
            onClick={() => createGoal.mutate()}
            variant="contained"
          >
            Save target
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
