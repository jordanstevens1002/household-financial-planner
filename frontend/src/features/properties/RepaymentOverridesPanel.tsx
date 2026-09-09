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
import { useMemo, useState } from 'react';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';
import {
  personActiveForOverride,
  type RepaymentAllocationDraft,
  validateRepaymentOverride,
} from './repaymentOverrideValidation';

type Loan = components['schemas']['LoanRead'];
type Person = components['schemas']['PersonRead'];
type Responsibility = components['schemas']['LoanRepaymentResponsibilityRead'];
type ResponsibilitySet =
  components['schemas']['LoanRepaymentResponsibilitySetRead'];

interface OverrideRow {
  allocations: Responsibility[];
  effectiveFrom: string;
  effectiveTo: string | null;
}

const emptyAllocation = (): RepaymentAllocationDraft => ({
  notes: '',
  percentage: '',
  personId: '',
});

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

export function RepaymentOverridesPanel({
  canEdit,
  householdId,
  loans,
}: {
  canEdit: boolean;
  householdId: string;
  loans: Loan[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [open, setOpen] = useState(false);
  const [loanId, setLoanId] = useState(loans[0]?.id ?? '');
  const [effectiveFrom, setEffectiveFrom] = useState(localCalendarDate());
  const [effectiveTo, setEffectiveTo] = useState('');
  const [allocations, setAllocations] = useState<RepaymentAllocationDraft[]>([
    emptyAllocation(),
  ]);
  const [validationError, setValidationError] = useState('');
  const resetDraft = () => {
    setEffectiveFrom(localCalendarDate());
    setEffectiveTo('');
    setAllocations([emptyAllocation()]);
    setValidationError('');
  };
  const selectedLoan = loans.find((loan) => loan.id === loanId) ?? loans[0];
  const selectedLoanId = selectedLoan?.id ?? '';
  const people = useQuery({
    enabled: open,
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const history = useQuery({
    enabled: open && Boolean(selectedLoanId),
    queryFn: () =>
      apiRequest<Responsibility[]>(
        `/api/v1/loans/${selectedLoanId}/repayment-responsibilities`,
      ),
    queryKey: ['repayment-responsibilities', selectedLoanId],
    retry: false,
  });
  const rows = useMemo(() => {
    const grouped = new Map<string, OverrideRow>();
    for (const item of history.data ?? []) {
      const key = `${item.effective_from}:${item.effective_to ?? ''}`;
      const row = grouped.get(key) ?? {
        allocations: [],
        effectiveFrom: item.effective_from,
        effectiveTo: item.effective_to ?? null,
      };
      row.allocations.push(item);
      grouped.set(key, row);
    }
    return [...grouped.values()];
  }, [history.data]);
  const save = useMutation({
    mutationFn: (drafts: RepaymentAllocationDraft[]) =>
      apiRequest<ResponsibilitySet>(
        `/api/v1/loans/${selectedLoanId}/repayment-responsibilities/${effectiveFrom}?create_only=true`,
        {
          body: JSON.stringify({
            allocations: drafts.map((item) => ({
              notes: item.notes.trim() || null,
              person_id: item.personId,
              responsibility_percentage: item.percentage,
            })),
            effective_to: effectiveTo || null,
          }),
          csrfToken: auth.csrfToken(),
          method: 'PUT',
        },
      ),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setValidationError(
          'Another editor already added an override for this date. Review the refreshed history and choose another date.',
        );
        void queryClient.invalidateQueries({
          queryKey: ['repayment-responsibilities', selectedLoanId],
        });
      }
      notify(errorMessage(error), 'error');
    },
    onSuccess: async () => {
      setAllocations([emptyAllocation()]);
      setValidationError('');
      notify('Repayment override added', 'success');
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['repayment-responsibilities', selectedLoanId],
        }),
        queryClient.invalidateQueries({ queryKey: ['household-cashflow'] }),
      ]);
    },
  });
  const personName = (personId: string) =>
    people.data?.find((person) => person.id === personId)?.display_name ??
    'Unknown person';
  const borrowerDefaults = (selectedLoan?.borrower_person_ids ?? []).map(
    personName,
  );
  const columns: DataColumn<OverrideRow>[] = [
    {
      key: 'dates',
      label: 'Effective dates',
      render: (row) =>
        `${formatDate(row.effectiveFrom)} – ${row.effectiveTo ? formatDate(row.effectiveTo) : 'Ongoing'}`,
    },
    {
      key: 'allocations',
      label: 'Repayment allocation',
      render: (row) =>
        row.allocations
          .map(
            (item) =>
              `${personName(item.person_id)} ${item.responsibility_percentage}%`,
          )
          .join(', '),
    },
    {
      key: 'notes',
      label: 'Notes',
      render: (row) =>
        row.allocations
          .map((item) => item.notes)
          .filter(Boolean)
          .join('; ') || '—',
    },
  ];

  const submit = () => {
    const error = validateRepaymentOverride({
      allocations,
      effectiveFrom,
      effectiveTo,
      existingStartDates: rows.map((row) => row.effectiveFrom),
      people: people.data ?? [],
    });
    if (error) {
      setValidationError(error);
      return;
    }
    save.mutate(allocations);
  };

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="outlined">
        Advanced repayment overrides
      </Button>
      <Dialog
        fullWidth
        maxWidth="md"
        onClose={() => !save.isPending && setOpen(false)}
        open={open}
      >
        <DialogTitle>Advanced repayment overrides</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="warning">
              Borrowers are the ordinary repayment defaults. A dated override is
              for an unusual period where different people carry the repayment;
              the latest active start date takes precedence.
            </Alert>
            <TextField
              label="Loan"
              onChange={(event) => {
                setLoanId(event.target.value);
                resetDraft();
              }}
              select
              value={selectedLoanId}
            >
              {loans.map((loan) => (
                <MenuItem key={loan.id} value={loan.id}>
                  {loan.display_name}
                </MenuItem>
              ))}
            </TextField>
            <Typography>
              Borrower defaults:{' '}
              {borrowerDefaults.length
                ? borrowerDefaults.join(', ')
                : 'Whole household'}
            </Typography>
            {history.isPending || people.isPending ? (
              <CircularProgress
                aria-label="Loading repayment overrides"
                size={24}
              />
            ) : history.error || people.error ? (
              <Alert
                action={
                  <Button
                    onClick={() => {
                      void history.refetch();
                      void people.refetch();
                    }}
                  >
                    Retry
                  </Button>
                }
                severity="error"
              >
                Repayment overrides could not be loaded.{' '}
                {errorMessage(history.error ?? people.error)}
              </Alert>
            ) : rows.length ? (
              <DataTable
                caption="Repayment override history"
                columns={columns}
                getRowKey={(row) =>
                  `${row.effectiveFrom}:${row.effectiveTo ?? ''}`
                }
                rows={rows}
              />
            ) : (
              <EmptyState
                description="Borrower defaults currently apply for every date."
                title="No dated overrides"
              />
            )}
            {canEdit ? (
              <Stack spacing={2}>
                <Typography variant="h3">Add dated override</Typography>
                <Stack direction="row" spacing={2}>
                  <TextField
                    fullWidth
                    label="Effective from"
                    onChange={(event) => setEffectiveFrom(event.target.value)}
                    slotProps={{ inputLabel: { shrink: true } }}
                    type="date"
                    value={effectiveFrom}
                  />
                  <TextField
                    fullWidth
                    label="Effective to (optional)"
                    onChange={(event) => setEffectiveTo(event.target.value)}
                    slotProps={{ inputLabel: { shrink: true } }}
                    type="date"
                    value={effectiveTo}
                  />
                </Stack>
                {allocations.map((allocation, index) => (
                  <Stack direction="row" key={index} spacing={2}>
                    <TextField
                      disabled={people.isPending || Boolean(people.error)}
                      fullWidth
                      label={`Person ${index + 1}`}
                      onChange={(event) =>
                        setAllocations((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, personId: event.target.value }
                              : item,
                          ),
                        )
                      }
                      select
                      value={allocation.personId}
                    >
                      {(people.data ?? []).map((person) => (
                        <MenuItem key={person.id} value={person.id}>
                          {person.display_name}
                          {!personActiveForOverride(
                            person,
                            effectiveFrom,
                            effectiveTo,
                          )
                            ? ' (inactive for these dates)'
                            : ''}
                        </MenuItem>
                      ))}
                    </TextField>
                    <TextField
                      label="Share %"
                      onChange={(event) =>
                        setAllocations((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, percentage: event.target.value }
                              : item,
                          ),
                        )
                      }
                      value={allocation.percentage}
                    />
                    <TextField
                      error={allocation.notes.length > 2_000}
                      fullWidth
                      helperText={`${allocation.notes.length.toLocaleString()} / 2,000 characters`}
                      label="Notes (optional)"
                      onChange={(event) =>
                        setAllocations((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, notes: event.target.value }
                              : item,
                          ),
                        )
                      }
                      slotProps={{ htmlInput: { maxLength: 2_000 } }}
                      value={allocation.notes}
                    />
                    {allocations.length > 1 ? (
                      <Button
                        onClick={() =>
                          setAllocations((current) =>
                            current.filter(
                              (_, itemIndex) => itemIndex !== index,
                            ),
                          )
                        }
                      >
                        Remove
                      </Button>
                    ) : null}
                  </Stack>
                ))}
                <Button
                  disabled={allocations.length >= 20}
                  onClick={() =>
                    setAllocations((current) => [...current, emptyAllocation()])
                  }
                  sx={{ alignSelf: 'flex-start' }}
                >
                  Add person
                </Button>
                {validationError ? (
                  <Alert severity="error">{validationError}</Alert>
                ) : null}
                {save.error ? (
                  <Alert severity="error">
                    The override could not be saved. {errorMessage(save.error)}
                  </Alert>
                ) : null}
              </Stack>
            ) : (
              <Alert severity="info">
                You can review overrides, but only an editor can add one.
              </Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={save.isPending} onClick={() => setOpen(false)}>
            Close
          </Button>
          {canEdit ? (
            <Button
              disabled={
                save.isPending ||
                history.isPending ||
                people.isPending ||
                Boolean(history.error || people.error)
              }
              onClick={submit}
              variant="contained"
            >
              Save override
            </Button>
          ) : null}
        </DialogActions>
      </Dialog>
    </>
  );
}
