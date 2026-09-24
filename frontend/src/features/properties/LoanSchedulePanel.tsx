import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { formatCurrency, formatDate } from '../../shared/format';

type Loan = components['schemas']['LoanRead'];
type Schedule = components['schemas']['LoanScheduleRead'];
type ScheduleEntry = components['schemas']['ScheduleEntry'];

const PAGE_SIZE = 25;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function SummaryValue({ label, value }: { label: string; value: string }) {
  return (
    <Paper sx={{ flex: '1 1 180px', p: 2 }} variant="outlined">
      <Typography color="text.secondary" variant="body2">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }} variant="h6">
        {value}
      </Typography>
    </Paper>
  );
}

function QualityInfo({ flags }: { flags: string[] }) {
  if (!flags.length) return null;
  return (
    <Tooltip arrow title={flags.join(', ')}>
      <IconButton
        aria-label={`Schedule warnings: ${flags.join(', ')}`}
        size="small"
      >
        <Typography aria-hidden="true" component="span">
          ⓘ
        </Typography>
      </IconButton>
    </Tooltip>
  );
}

export function LoanSchedulePanel({ loans }: { loans: Loan[] }) {
  const [open, setOpen] = useState(false);
  const [loanId, setLoanId] = useState(loans[0]?.id ?? '');
  const [draftThroughDate, setDraftThroughDate] = useState('');
  const [throughDate, setThroughDate] = useState('');
  const [page, setPage] = useState(0);
  const selectedLoan = (loans.find((loan) => loan.id === loanId) ?? loans[0])!;
  const selectedLoanId = selectedLoan.id;
  const schedule = useQuery({
    enabled: open && Boolean(selectedLoanId),
    queryFn: () => {
      const query = new URLSearchParams({
        entry_limit: String(PAGE_SIZE),
        entry_offset: String(page * PAGE_SIZE),
      });
      if (throughDate) query.set('through_date', throughDate);
      return apiRequest<Schedule>(
        `/api/v1/loans/${selectedLoanId}/schedule?${query.toString()}`,
      );
    },
    queryKey: ['loan-schedule', selectedLoanId, throughDate, page],
    retry: false,
  });
  const entries = schedule.data?.entries ?? [];
  const pageCount = Math.max(
    1,
    Math.ceil((schedule.data?.entry_total ?? 0) / PAGE_SIZE),
  );

  const columns: DataColumn<ScheduleEntry>[] = [
    { key: 'number', label: '#', render: (entry) => entry.payment_number },
    {
      key: 'date',
      label: 'Payment date',
      render: (entry) => formatDate(entry.payment_date),
    },
    {
      key: 'opening',
      label: 'Opening balance',
      render: (entry) =>
        formatCurrency(entry.opening_balance, selectedLoan.currency),
    },
    {
      key: 'interest',
      label: 'Interest',
      render: (entry) => formatCurrency(entry.interest, selectedLoan.currency),
    },
    {
      key: 'repayment',
      label: 'Repayment',
      render: (entry) => formatCurrency(entry.repayment, selectedLoan.currency),
    },
    {
      key: 'principal',
      label: 'Principal',
      render: (entry) => formatCurrency(entry.principal, selectedLoan.currency),
    },
    {
      key: 'offset',
      label: 'Offset',
      render: (entry) =>
        formatCurrency(entry.offset_balance, selectedLoan.currency),
    },
    {
      key: 'closing',
      label: 'Closing balance',
      render: (entry) =>
        formatCurrency(entry.closing_balance, selectedLoan.currency),
    },
    {
      key: 'rate',
      label: 'Rate',
      render: (entry) => `${entry.annual_interest_rate}%`,
    },
  ];

  const changeLoan = (nextLoanId: string) => {
    setLoanId(nextLoanId);
    setDraftThroughDate('');
    setThroughDate('');
    setPage(0);
  };

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="outlined">
        Analyse schedule
      </Button>
      <Dialog
        fullWidth
        maxWidth="xl"
        onClose={() => setOpen(false)}
        open={open}
      >
        <DialogTitle>Loan schedule analysis</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              This schedule is calculated by the API from the recorded loan and
              dated events. It is a planning estimate, not a lender statement.
            </Alert>
            <Stack direction="row" spacing={2}>
              <TextField
                fullWidth
                label="Loan"
                onChange={(event) => changeLoan(event.target.value)}
                select
                value={selectedLoanId}
              >
                {loans.map((loan) => (
                  <MenuItem key={loan.id} value={loan.id}>
                    {loan.display_name}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                fullWidth
                helperText="Optional. Required when the loan has no recorded term."
                label="Calculate through"
                onChange={(event) => setDraftThroughDate(event.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                type="date"
                value={draftThroughDate}
              />
              <Button
                onClick={() => {
                  setPage(0);
                  if (draftThroughDate === throughDate) void schedule.refetch();
                  else setThroughDate(draftThroughDate);
                }}
                variant="outlined"
              >
                Calculate
              </Button>
            </Stack>
            <Typography color="text.secondary" variant="body2">
              Assumptions: opening balance{' '}
              {formatCurrency(
                selectedLoan.opening_balance,
                selectedLoan.currency,
              )}{' '}
              on {formatDate(selectedLoan.opening_balance_date)};{' '}
              {selectedLoan.initial_interest_rate}% annual rate;{' '}
              {selectedLoan.scheduled_repayment == null
                ? 'no fixed repayment recorded'
                : `${formatCurrency(selectedLoan.scheduled_repayment, selectedLoan.currency)} ${selectedLoan.repayment_frequency.toLowerCase()}`}
              ; {selectedLoan.interest_calculation_method.toLowerCase()}{' '}
              interest;{' '}
              {selectedLoan.term_months == null
                ? 'no fixed term recorded'
                : `${selectedLoan.term_months} month term`}
              .
            </Typography>
            {schedule.isPending ? (
              <CircularProgress
                aria-label="Calculating loan schedule"
                size={24}
              />
            ) : schedule.error ? (
              <Alert
                action={
                  <Button onClick={() => void schedule.refetch()}>Retry</Button>
                }
                severity="error"
              >
                Schedule could not be calculated. {errorMessage(schedule.error)}
              </Alert>
            ) : schedule.data ? (
              <Stack spacing={2}>
                <Stack
                  direction="row"
                  spacing={1}
                  sx={{ alignItems: 'center' }}
                >
                  <Typography variant="h3">Calculated position</Typography>
                  <QualityInfo flags={schedule.data.data_quality_flags} />
                </Stack>
                <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
                  <SummaryValue
                    label="Total repayments"
                    value={formatCurrency(
                      schedule.data.total_repayments,
                      selectedLoan.currency,
                    )}
                  />
                  <SummaryValue
                    label="Total interest"
                    value={formatCurrency(
                      schedule.data.total_interest,
                      selectedLoan.currency,
                    )}
                  />
                  <SummaryValue
                    label="Remaining balance"
                    value={formatCurrency(
                      schedule.data.remaining_balance,
                      selectedLoan.currency,
                    )}
                  />
                  <SummaryValue
                    label="Estimated payoff"
                    value={
                      schedule.data.payoff_date
                        ? formatDate(schedule.data.payoff_date)
                        : 'Not paid off in this period'
                    }
                  />
                  {schedule.data.interest_saved_vs_no_offset != null ? (
                    <SummaryValue
                      label="Estimated offset interest saved"
                      value={formatCurrency(
                        schedule.data.interest_saved_vs_no_offset,
                        selectedLoan.currency,
                      )}
                    />
                  ) : null}
                </Stack>
                {entries.length ? (
                  <>
                    <DataTable
                      caption="Loan balance progression"
                      columns={columns}
                      getRowKey={(entry) =>
                        `${entry.payment_number}-${entry.payment_date}`
                      }
                      rows={entries}
                    />
                    <Stack
                      direction="row"
                      sx={{ alignItems: 'center', justifyContent: 'flex-end' }}
                    >
                      <Button
                        disabled={page === 0 || schedule.isFetching}
                        onClick={() => setPage(page - 1)}
                      >
                        Previous
                      </Button>
                      <Typography aria-live="polite" sx={{ px: 2 }}>
                        Page {page + 1} of {pageCount} ·{' '}
                        {schedule.data.entry_total} payments
                      </Typography>
                      <Button
                        disabled={
                          !schedule.data.has_more || schedule.isFetching
                        }
                        onClick={() => setPage(page + 1)}
                      >
                        Next
                      </Button>
                    </Stack>
                  </>
                ) : (
                  <Alert severity="info">
                    No scheduled payments occur in this period.
                  </Alert>
                )}
              </Stack>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
