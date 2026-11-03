import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { localCalendarDate } from '../people/localDate';

type Account = components['schemas']['RetirementAccountRead'];
type Entry = components['schemas']['RetirementProjectionEntry'];
type Projection = components['schemas']['RetirementProjectionRead'];

const pageSize = 12;
const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The calculation failed';

function Metric({
  currency,
  label,
  value,
}: {
  currency: string;
  label: string;
  value: string;
}) {
  return (
    <Paper sx={{ flex: '1 1 170px', p: 2 }} variant="outlined">
      <Typography color="text.secondary" variant="body2">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }} variant="h6">
        {formatCurrency(value, currency)}
      </Typography>
    </Paper>
  );
}

function WarningInfo({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <Tooltip
      arrow
      title={
        <Stack component="ul" spacing={1} sx={{ m: 0, pl: 2 }}>
          {warnings.map((warning, index) => (
            <li key={`${index}-${warning}`}>{warning}</li>
          ))}
        </Stack>
      }
    >
      <IconButton
        aria-label={`${warnings.length} projection warnings`}
        size="small"
      >
        <Typography aria-hidden sx={{ fontWeight: 700 }}>
          ⓘ
        </Typography>
      </IconButton>
    </Tooltip>
  );
}

export function RetirementProjectionDialog({
  account,
  onClose,
  providerName,
}: {
  account: Account;
  onClose: () => void;
  providerName?: string;
}) {
  const [projectionDate, setProjectionDate] = useState(() =>
    localCalendarDate() < account.opening_balance_date
      ? account.opening_balance_date
      : localCalendarDate(),
  );
  const [validation, setValidation] = useState('');
  const [page, setPage] = useState(0);
  const calculation = useMutation({
    mutationFn: (date: string) =>
      apiRequest<Projection>(
        `/api/v1/retirement-accounts/${account.id}/projection?projection_date=${date}`,
      ),
    onSuccess: () => setPage(0),
  });
  const calculate = () => {
    setValidation('');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(projectionDate))
      return setValidation('Enter a valid projection date.');
    if (projectionDate < account.opening_balance_date)
      return setValidation(
        'Projection date cannot precede the opening balance date.',
      );
    calculation.mutate(projectionDate);
  };
  const result = calculation.data;
  const entries = result?.entries ?? [];
  const pages = Math.max(1, Math.ceil(entries.length / pageSize));
  const visibleEntries = entries.slice(page * pageSize, (page + 1) * pageSize);
  const columns: DataColumn<Entry>[] = [
    {
      key: 'date',
      label: 'Projection date',
      render: (item) => formatDate(item.projection_date),
    },
    {
      key: 'employer',
      label: 'Employer',
      render: (item) =>
        formatCurrency(
          item.employer_contributions,
          result?.currency ?? account.currency,
        ),
    },
    {
      key: 'pre-tax',
      label: 'Pre-tax',
      render: (item) =>
        formatCurrency(
          item.voluntary_pre_tax_contributions,
          result?.currency ?? account.currency,
        ),
    },
    {
      key: 'post-tax',
      label: 'Post-tax',
      render: (item) =>
        formatCurrency(
          item.voluntary_post_tax_contributions,
          result?.currency ?? account.currency,
        ),
    },
    {
      key: 'adjustments',
      label: 'Adjustments',
      render: (item) =>
        formatCurrency(
          item.balance_adjustments,
          result?.currency ?? account.currency,
        ),
    },
    {
      key: 'earnings',
      label: 'Earnings',
      render: (item) =>
        formatCurrency(item.earnings, result?.currency ?? account.currency),
    },
    {
      key: 'fees',
      label: 'Fees',
      render: (item) =>
        formatCurrency(item.fees, result?.currency ?? account.currency),
    },
    {
      key: 'tax',
      label: 'Tax',
      render: (item) =>
        formatCurrency(
          item.contribution_tax,
          result?.currency ?? account.currency,
        ),
    },
    {
      key: 'balance',
      label: 'Closing balance',
      render: (item) =>
        formatCurrency(
          item.closing_balance,
          result?.currency ?? account.currency,
        ),
    },
  ];
  return (
    <Dialog fullWidth maxWidth="lg" onClose={onClose} open>
      <DialogTitle>{account.display_name} — projection</DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ pt: 1 }}>
          <Typography color="text.secondary">
            Explore a dated estimate calculated by the backend. This does not
            change household records.
          </Typography>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Projection date"
              onChange={(event) => {
                setProjectionDate(event.target.value);
                setValidation('');
                calculation.reset();
              }}
              slotProps={{ inputLabel: { shrink: true } }}
              type="date"
              value={projectionDate}
            />
            <Button
              disabled={calculation.isPending}
              onClick={calculate}
              variant="contained"
            >
              Calculate
            </Button>
          </Stack>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {calculation.isPending ? (
            <CircularProgress aria-label="Calculating retirement projection" />
          ) : calculation.error ? (
            <Alert severity="error">
              Projection could not be calculated. {message(calculation.error)}
            </Alert>
          ) : result ? (
            <>
              <Stack direction="row" sx={{ alignItems: 'center', gap: 1 }}>
                <Typography>
                  Results to {formatDate(result.projection_date)} using{' '}
                  {result.provider_code
                    ? (providerName ?? `${result.provider_code} provider`)
                    : 'generic account assumptions'}
                  .
                </Typography>
                <WarningInfo warnings={result.warnings} />
              </Stack>
              <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
                <Metric
                  currency={result.currency}
                  label="Projected balance"
                  value={result.projected_balance}
                />
                <Metric
                  currency={result.currency}
                  label="Contributions"
                  value={result.total_contributions}
                />
                <Metric
                  currency={result.currency}
                  label="Earnings"
                  value={result.total_earnings}
                />
                <Metric
                  currency={result.currency}
                  label="Fees"
                  value={result.total_fees}
                />
                <Metric
                  currency={result.currency}
                  label="Contribution tax"
                  value={result.total_contribution_tax}
                />
              </Stack>
              {entries.length ? (
                <Box>
                  <DataTable
                    caption="Retirement projection periods"
                    columns={columns}
                    getRowKey={(item) => item.projection_date}
                    rows={visibleEntries}
                  />
                  <Stack
                    direction="row"
                    sx={{
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      mt: 1,
                    }}
                  >
                    <Button
                      disabled={page === 0}
                      onClick={() => setPage(page - 1)}
                    >
                      Previous
                    </Button>
                    <Typography variant="body2">
                      Page {page + 1} of {pages}
                    </Typography>
                    <Button
                      disabled={page + 1 >= pages}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </Button>
                  </Stack>
                </Box>
              ) : (
                <Alert severity="info">
                  The projection date is the opening date, so there are no
                  projection periods yet.
                </Alert>
              )}
              <AdvancedSection description="Review the assumptions supplied by the backend for this estimate.">
                <Stack component="ul" spacing={1} sx={{ m: 0, pl: 2 }}>
                  {result.assumptions_used.map((assumption, index) => (
                    <li key={`${index}-${assumption}`}>{assumption}</li>
                  ))}
                </Stack>
              </AdvancedSection>
            </>
          ) : (
            <EmptyState
              description="Choose a future date to calculate contributions, earnings, fees, tax and balance."
              title="No projection calculated"
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
