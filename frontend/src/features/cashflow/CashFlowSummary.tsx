import {
  Alert,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency } from '../../shared/format';
import { localCalendarDate } from '../people/localDate';

type Cashflow = components['schemas']['HouseholdCashflowRead'];
type PersonProjection = components['schemas']['PersonIncomeProjection'];
type LoanProjection = components['schemas']['LoanRepaymentProjectionRead'];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function validDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function SummaryAmount({
  currency,
  label,
  value,
}: {
  currency: string;
  label: string;
  value: string;
}) {
  return (
    <Paper sx={{ flex: '1 1 180px', p: 2 }} variant="outlined">
      <Typography color="text.secondary" variant="body2">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }} variant="h6">
        {formatCurrency(value, currency)}
      </Typography>
    </Paper>
  );
}

export function CashFlowSummary({
  currency,
  householdId,
}: {
  currency: string;
  householdId: string;
}) {
  const [asOf, setAsOf] = useState(localCalendarDate());
  const [draftDate, setDraftDate] = useState(asOf);
  const [dateError, setDateError] = useState('');
  const projection = useQuery({
    queryFn: () =>
      apiRequest<Cashflow>(
        `/api/v1/households/${householdId}/cashflow?as_of=${asOf}`,
      ),
    queryKey: ['household-cashflow', householdId, asOf],
    retry: false,
  });
  const displayCurrency = projection.data?.currency ?? currency;
  const dateIsDirty = draftDate !== asOf;

  const applyDate = () => {
    if (!validDate(draftDate)) {
      setDateError('Use YYYY-MM-DD');
      return;
    }
    setDateError('');
    if (draftDate === asOf) {
      void projection.refetch();
    } else {
      setAsOf(draftDate);
    }
  };

  const personColumns: DataColumn<PersonProjection>[] = [
    { key: 'person', label: 'Person', render: (row) => row.display_name },
    {
      key: 'gross',
      label: 'Gross taxable',
      render: (row) =>
        formatCurrency(row.gross_taxable_income, displayCurrency),
    },
    {
      key: 'non-taxable',
      label: 'Non-taxable',
      render: (row) => formatCurrency(row.non_taxable_income, displayCurrency),
    },
    {
      key: 'tax',
      label: 'Tax & repayments',
      render: (row) => formatCurrency(row.tax_and_repayments, displayCurrency),
    },
    {
      key: 'net',
      label: 'Net income',
      render: (row) => formatCurrency(row.net_income, displayCurrency),
    },
    {
      key: 'method',
      label: 'Tax method',
      render: (row) => row.calculation_mode,
    },
    {
      key: 'warnings',
      label: 'Warnings',
      render: (row) =>
        row.warnings.length
          ? `${row.display_name}: ${row.warnings.join(' ')}`
          : 'None',
    },
  ];
  const loanColumns: DataColumn<LoanProjection>[] = [
    { key: 'loan', label: 'Loan', render: (row) => row.display_name },
    {
      key: 'periodic',
      label: 'Regular repayment',
      render: (row) =>
        `${formatCurrency(row.periodic_repayment, row.currency)} ${row.repayment_frequency.toLowerCase()}`,
    },
    {
      key: 'monthly',
      label: 'Monthly',
      render: (row) => formatCurrency(row.monthly_repayment, row.currency),
    },
    {
      key: 'annual',
      label: 'Annual',
      render: (row) => formatCurrency(row.annual_repayment, row.currency),
    },
    {
      key: 'responsibility',
      label: 'Responsibility',
      render: (row) =>
        row.allocations.length
          ? row.allocations
              .map(
                (item) =>
                  `${item.display_name} ${item.responsibility_percentage}%`,
              )
              .join(', ')
          : 'Whole household',
    },
    {
      key: 'included',
      label: 'Included in total',
      render: (row) => (row.included_in_household_total ? 'Yes' : 'No'),
    },
    {
      key: 'warnings',
      label: 'Warnings',
      render: (row) =>
        row.warnings.length
          ? `${row.display_name}: ${row.warnings.join(' ')}`
          : 'None',
    },
  ];

  return (
    <Stack spacing={2}>
      <Typography variant="h2">Position at a date</Typography>
      <Stack direction="row" spacing={2} sx={{ alignItems: 'flex-start' }}>
        <TextField
          error={Boolean(dateError)}
          helperText={dateError}
          label="Position date"
          onChange={(event) => setDraftDate(event.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          type="date"
          value={draftDate}
        />
        <Button onClick={applyDate} variant="outlined">
          Refresh position
        </Button>
      </Stack>
      {projection.isPending ? (
        <CircularProgress aria-label="Loading cash-flow position" />
      ) : projection.error ? (
        <Alert
          action={
            <Button color="inherit" onClick={() => void projection.refetch()}>
              Retry
            </Button>
          }
          severity="error"
        >
          Cash-flow position could not be loaded.{' '}
          {errorMessage(projection.error)}
        </Alert>
      ) : projection.data ? (
        <Stack spacing={3}>
          <Alert severity={dateIsDirty ? 'info' : 'success'}>
            Results as of {projection.data.as_of}.
            {dateIsDirty
              ? ' The position date has changed; refresh to calculate it.'
              : ''}
          </Alert>
          {projection.data.currency !== currency ? (
            <Alert severity="warning">
              The calculation returned {projection.data.currency}, while this
              household is recorded in {currency}.
            </Alert>
          ) : null}
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
            <SummaryAmount
              currency={displayCurrency}
              label="Annual gross income"
              value={projection.data.annual_gross_income}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Annual net income"
              value={projection.data.annual_net_income}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Annual ordinary expenses"
              value={projection.data.annual_ordinary_expenses}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Annual loan repayments"
              value={projection.data.annual_loan_repayments}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Annual total expenses"
              value={projection.data.annual_expenses}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Annual surplus"
              value={projection.data.annual_surplus}
            />
          </Stack>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
            <SummaryAmount
              currency={displayCurrency}
              label="Monthly net income"
              value={projection.data.monthly_net_income}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Monthly ordinary expenses"
              value={projection.data.monthly_ordinary_expenses}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Monthly loan repayments"
              value={projection.data.monthly_loan_repayments}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Monthly total expenses"
              value={projection.data.monthly_expenses}
            />
            <SummaryAmount
              currency={displayCurrency}
              label="Monthly surplus"
              value={projection.data.monthly_surplus}
            />
          </Stack>
          <Typography variant="h2">Income and tax by person</Typography>
          {projection.data.people.length ? (
            <DataTable
              caption="Person cash-flow projections"
              columns={personColumns}
              getRowKey={(row) => row.person_id}
              rows={projection.data.people}
            />
          ) : (
            <EmptyState
              description="Add people and income sources to calculate household income."
              title="No person income available"
            />
          )}
          <Typography variant="h2">Loan repayments</Typography>
          {projection.data.loan_repayments.length ? (
            <DataTable
              caption="Automatic loan repayments"
              columns={loanColumns}
              getRowKey={(row) => row.loan_id}
              rows={projection.data.loan_repayments}
            />
          ) : (
            <EmptyState
              description="No loan repayments are included at this date."
              title="No automatic loan repayments"
            />
          )}
        </Stack>
      ) : null}
    </Stack>
  );
}
