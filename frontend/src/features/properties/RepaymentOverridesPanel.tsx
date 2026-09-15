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
import { ConfirmDialog } from '../../shared/ConfirmDialog';
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

type EditMode = 'create' | 'correct' | 'close';

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
  const [mode, setMode] = useState<EditMode>('create');
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [expectedRevision, setExpectedRevision] = useState<{
    effectiveTo: string | null;
    responsibilityIds: string[];
  } | null>(null);
  const resetDraft = () => {
    setEffectiveFrom(localCalendarDate());
    setEffectiveTo('');
    setAllocations([emptyAllocation()]);
    setValidationError('');
    setMode('create');
    setExpectedRevision(null);
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
    mutationFn: (drafts: RepaymentAllocationDraft[]) => {
      if (mode === 'close') {
        return apiRequest<ResponsibilitySet>(
          `/api/v1/loans/${selectedLoanId}/repayment-responsibilities/${effectiveFrom}/closure`,
          {
            body: JSON.stringify({
              effective_to: effectiveTo,
              expected_revision: {
                effective_to: expectedRevision?.effectiveTo ?? null,
                responsibility_ids: expectedRevision?.responsibilityIds ?? [],
              },
            }),
            csrfToken: auth.csrfToken(),
            method: 'PATCH',
          },
        );
      }
      return apiRequest<ResponsibilitySet>(
        `/api/v1/loans/${selectedLoanId}/repayment-responsibilities/${effectiveFrom}${mode === 'create' ? '?create_only=true' : ''}`,
        {
          body: JSON.stringify({
            allocations: drafts.map((item) => ({
              notes: item.notes.trim() || null,
              person_id: item.personId,
              responsibility_percentage: item.percentage,
            })),
            effective_to: effectiveTo || null,
            ...(mode === 'correct'
              ? {
                  expected_revision: {
                    effective_to: expectedRevision?.effectiveTo ?? null,
                    responsibility_ids:
                      expectedRevision?.responsibilityIds ?? [],
                  },
                }
              : {}),
          }),
          csrfToken: auth.csrfToken(),
          method: 'PUT',
        },
      );
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        const message =
          mode === 'create'
            ? 'Another editor already added an override for this date. Review the refreshed history and choose another date.'
            : 'Another editor changed this override. Review the refreshed history before trying again.';
        setConfirmationOpen(false);
        resetDraft();
        setValidationError(message);
        void queryClient.invalidateQueries({
          queryKey: ['repayment-responsibilities', selectedLoanId],
        });
      }
      notify(errorMessage(error), 'error');
    },
    onSuccess: async () => {
      const action =
        mode === 'create' ? 'added' : mode === 'close' ? 'ended' : 'corrected';
      setConfirmationOpen(false);
      resetDraft();
      notify(`Repayment override ${action}`, 'success');
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
    ...(canEdit
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (row: OverrideRow) => (
              <Stack direction="row" spacing={1}>
                <Button
                  onClick={() => {
                    setMode('correct');
                    setEffectiveFrom(row.effectiveFrom);
                    setEffectiveTo(row.effectiveTo ?? '');
                    setAllocations(
                      row.allocations.map((item) => ({
                        notes: item.notes ?? '',
                        percentage: item.responsibility_percentage,
                        personId: item.person_id,
                      })),
                    );
                    setExpectedRevision({
                      effectiveTo: row.effectiveTo,
                      responsibilityIds: row.allocations.map((item) => item.id),
                    });
                    setValidationError('');
                  }}
                >
                  Correct
                </Button>
                <Button
                  disabled={row.effectiveTo != null}
                  onClick={() => {
                    setMode('close');
                    setEffectiveFrom(row.effectiveFrom);
                    setEffectiveTo('');
                    setAllocations(
                      row.allocations.map((item) => ({
                        notes: item.notes ?? '',
                        percentage: item.responsibility_percentage,
                        personId: item.person_id,
                      })),
                    );
                    setExpectedRevision({
                      effectiveTo: row.effectiveTo,
                      responsibilityIds: row.allocations.map((item) => item.id),
                    });
                    setValidationError('');
                  }}
                >
                  End
                </Button>
              </Stack>
            ),
          },
        ]
      : []),
  ];

  const submit = () => {
    if (mode === 'close') {
      if (!effectiveTo || effectiveTo < effectiveFrom) {
        setValidationError('Choose an end date on or after the start date');
        return;
      }
      setConfirmationOpen(true);
      return;
    }
    const error = validateRepaymentOverride({
      allocations,
      effectiveFrom,
      effectiveTo,
      existingStartDates: rows
        .map((row) => row.effectiveFrom)
        .filter((start) => mode === 'create' || start !== effectiveFrom),
      people: people.data ?? [],
    });
    if (error) {
      setValidationError(error);
      return;
    }
    if (mode === 'correct') setConfirmationOpen(true);
    else save.mutate(allocations);
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
                <Typography variant="h3">
                  {mode === 'create'
                    ? 'Add dated override'
                    : mode === 'close'
                      ? 'End dated override'
                      : 'Correct dated override'}
                </Typography>
                <Stack direction="row" spacing={2}>
                  <TextField
                    disabled={mode !== 'create'}
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
                {mode !== 'close' &&
                  allocations.map((allocation, index) => (
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
                {mode !== 'close' ? (
                  <Button
                    disabled={allocations.length >= 20}
                    onClick={() =>
                      setAllocations((current) => [
                        ...current,
                        emptyAllocation(),
                      ])
                    }
                    sx={{ alignSelf: 'flex-start' }}
                  >
                    Add person
                  </Button>
                ) : null}
                {mode !== 'create' ? (
                  <Button onClick={resetDraft} sx={{ alignSelf: 'flex-start' }}>
                    Cancel change
                  </Button>
                ) : null}
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
              {mode === 'create'
                ? 'Save override'
                : mode === 'close'
                  ? 'End override'
                  : 'Save correction'}
            </Button>
          ) : null}
        </DialogActions>
      </Dialog>
      <ConfirmDialog
        confirmLabel={mode === 'close' ? 'End override' : 'Save correction'}
        description={
          mode === 'close'
            ? `End this repayment override on ${effectiveTo}? Its earlier history will remain recorded.`
            : 'Replace this dated allocation set with the corrected values? Both versions will remain in the audit history.'
        }
        onCancel={() => setConfirmationOpen(false)}
        onConfirm={() => save.mutate(allocations)}
        open={confirmationOpen}
        pending={save.isPending}
        title={
          mode === 'close'
            ? 'End repayment override?'
            : 'Save corrected allocation?'
        }
      />
    </>
  );
}
