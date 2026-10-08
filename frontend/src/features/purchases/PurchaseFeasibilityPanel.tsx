import {
  Alert,
  Box,
  Button,
  CircularProgress,
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
import { formatCurrency, formatDate } from '../../shared/format';
import { useAuth } from '../auth/AuthContext';
import {
  type FeasibilityDraft,
  validateFeasibilityDraft,
} from './purchaseFeasibilityValidation';

type Detail = components['schemas']['PurchasePlanDetail'];
type Result = components['schemas']['FeasibilityRead'];
type Cost = components['schemas']['CalculatedCost'];
const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The calculation failed';

const initialDraft = (plan: Detail): FeasibilityDraft => ({
  annualInterestRate: '6',
  currentMonthlySurplus: '0',
  desiredBuffer: plan.desired_buffer,
  loanTermYears: '30',
  maximumAdditionalBorrowing: '0',
  purchasePrice: plan.target_price_min,
});

function Metric({ label, value }: { label: string; value: string }) {
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
      <IconButton aria-label={`${warnings.length} calculation warnings`}>
        <Typography aria-hidden sx={{ fontWeight: 700 }}>
          ⓘ
        </Typography>
      </IconButton>
    </Tooltip>
  );
}

export function PurchaseFeasibilityPanel({ plan }: { plan: Detail }) {
  const auth = useAuth();
  const [draft, setDraft] = useState(() => initialDraft(plan));
  const [providerSettings, setProviderSettings] = useState(() =>
    JSON.stringify(plan.provider_settings, null, 2),
  );
  const [validation, setValidation] = useState('');
  const calculation = useMutation({
    mutationFn: (body: components['schemas']['FeasibilityRequest']) =>
      apiRequest<Result>(`/api/v1/purchase-plans/${plan.id}/calculate`, {
        body: JSON.stringify(body),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
  });
  const field =
    (key: keyof FeasibilityDraft) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setDraft((current) => ({ ...current, [key]: event.target.value }));
      setValidation('');
      calculation.reset();
    };
  const submit = () => {
    setValidation('');
    const problem = validateFeasibilityDraft(draft);
    if (problem) return setValidation(problem);
    let parsedProviderSettings: Record<string, unknown> | null = null;
    if (plan.provider_code) {
      try {
        const parsed = JSON.parse(providerSettings) as unknown;
        if (
          typeof parsed !== 'object' ||
          parsed === null ||
          Array.isArray(parsed)
        )
          throw new Error();
        parsedProviderSettings = parsed as Record<string, unknown>;
      } catch {
        return setValidation('Provider settings must be a valid JSON object.');
      }
    }
    calculation.mutate({
      annual_interest_rate: draft.annualInterestRate,
      current_monthly_surplus: draft.currentMonthlySurplus,
      desired_buffer: draft.desiredBuffer || null,
      loan_term_years: Number(draft.loanTermYears),
      maximum_additional_borrowing: draft.maximumAdditionalBorrowing,
      provider_settings: parsedProviderSettings,
      purchase_price: draft.purchasePrice,
    });
  };
  const result = calculation.data;
  const costColumns: DataColumn<Cost>[] = [
    { key: 'name', label: 'Cost', render: (cost) => cost.display_name },
    { key: 'code', label: 'Code', render: (cost) => cost.code },
    {
      key: 'amount',
      label: `Amount (${plan.currency})`,
      render: (cost) => formatCurrency(cost.amount, plan.currency),
    },
    {
      key: 'source',
      label: 'Source',
      render: (cost) =>
        cost.source === 'USER' ? 'Household entry' : `${cost.source} provider`,
    },
  ];
  return (
    <Stack spacing={2}>
      <Box>
        <Typography component="h2" variant="h6">
          Purchase feasibility
        </Typography>
        <Typography color="text.secondary">
          Explore affordability using explicit assumptions. This calculation
          does not change household records.
        </Typography>
      </Box>
      <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
        <TextField
          fullWidth
          label={`Purchase price (${plan.currency})`}
          onChange={field('purchasePrice')}
          value={draft.purchasePrice}
        />
        <TextField
          fullWidth
          label={`Maximum additional borrowing (${plan.currency})`}
          onChange={field('maximumAdditionalBorrowing')}
          value={draft.maximumAdditionalBorrowing}
        />
        <TextField
          fullWidth
          label={`Current monthly surplus (${plan.currency})`}
          onChange={field('currentMonthlySurplus')}
          value={draft.currentMonthlySurplus}
        />
        <TextField
          fullWidth
          helperText="Leave blank to use the saved plan buffer"
          label={`Desired buffer (${plan.currency})`}
          onChange={field('desiredBuffer')}
          value={draft.desiredBuffer}
        />
      </Stack>
      <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
        <TextField
          fullWidth
          label="Annual interest rate (%)"
          onChange={field('annualInterestRate')}
          value={draft.annualInterestRate}
        />
        <TextField
          fullWidth
          label="Loan term (years)"
          onChange={field('loanTermYears')}
          value={draft.loanTermYears}
        />
        <Button
          disabled={calculation.isPending}
          onClick={submit}
          variant="contained"
        >
          Calculate
        </Button>
      </Stack>
      <Alert severity="info">
        Saved comfort settings: desired buffer{' '}
        {formatCurrency(plan.desired_buffer, plan.currency)}; maximum LVR{' '}
        {plan.max_lvr === null ? 'not set' : `${plan.max_lvr}%`}; minimum
        monthly surplus{' '}
        {plan.minimum_monthly_surplus === null
          ? 'not set'
          : formatCurrency(plan.minimum_monthly_surplus, plan.currency)}
        .
      </Alert>
      {plan.provider_code ? (
        <AdvancedSection
          description={`Configure calculation-only settings for ${plan.provider_code}. Changes here do not modify the saved plan.`}
        >
          <TextField
            label="Provider settings (JSON)"
            multiline
            minRows={4}
            onChange={(event) => {
              setProviderSettings(event.target.value);
              setValidation('');
              calculation.reset();
            }}
            value={providerSettings}
          />
        </AdvancedSection>
      ) : null}
      {validation ? <Alert severity="error">{validation}</Alert> : null}
      {calculation.isPending ? (
        <CircularProgress aria-label="Calculating purchase feasibility" />
      ) : null}
      {calculation.error ? (
        <Alert severity="error">
          Feasibility could not be calculated. {message(calculation.error)}
        </Alert>
      ) : null}
      {result ? (
        <Stack spacing={2}>
          <Stack direction="row" sx={{ alignItems: 'center' }}>
            <Alert
              severity={result.is_feasible ? 'success' : 'warning'}
              sx={{ flexGrow: 1 }}
            >
              {result.is_feasible
                ? 'This plan satisfies the saved comfort thresholds.'
                : 'This plan does not satisfy every saved comfort threshold.'}
            </Alert>
            <WarningInfo warnings={result.warnings} />
          </Stack>
          <Typography color="text.secondary" variant="body2">
            Calculated {formatDate(result.calculation_date)} using{' '}
            {result.currency}.
          </Typography>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 2 }}>
            <Metric
              label="Required total"
              value={formatCurrency(result.required_total, result.currency)}
            />
            <Metric
              label="Available non-borrowed funding"
              value={formatCurrency(
                result.available_equity_funding,
                result.currency,
              )}
            />
            <Metric
              label="Existing borrowed funding"
              value={formatCurrency(
                result.existing_borrowed_funding,
                result.currency,
              )}
            />
            <Metric
              label="Additional loan required"
              value={formatCurrency(
                result.additional_loan_required,
                result.currency,
              )}
            />
            <Metric
              label="Total debt funding"
              value={formatCurrency(result.total_debt_funding, result.currency)}
            />
            <Metric
              label="Funding gap"
              value={formatCurrency(result.funding_gap, result.currency)}
            />
            <Metric
              label="Monthly loan repayment"
              value={formatCurrency(
                result.monthly_loan_repayment,
                result.currency,
              )}
            />
            <Metric
              label="Projected monthly surplus"
              value={formatCurrency(
                result.projected_monthly_surplus,
                result.currency,
              )}
            />
            <Metric label="Loan-to-value ratio" value={`${result.lvr}%`} />
          </Stack>
          {result.failed_thresholds.length ? (
            <Alert severity="warning">
              <strong>Thresholds not met:</strong>{' '}
              {result.failed_thresholds.join('; ')}
            </Alert>
          ) : null}
          {result.costs.some((cost) => cost.source !== 'USER') &&
          result.costs
            .filter((cost) => cost.source !== 'USER')
            .every((cost) => Number(cost.amount) === 0) ? (
            <Alert severity="warning">
              The installed provider returned zero for every provider-derived
              cost. Review its settings before relying on this estimate.
            </Alert>
          ) : null}
          {result.costs.length ? (
            <DataTable
              caption="Calculated purchase costs"
              columns={costColumns}
              getRowKey={(cost) => `${cost.source}-${cost.code}`}
              rows={result.costs}
            />
          ) : (
            <Alert severity="info">No purchase costs were included.</Alert>
          )}
          <AdvancedSection description="Review the calculation assumptions used by the backend.">
            <Stack component="ul" spacing={1}>
              {result.assumptions_used.map((assumption, index) => (
                <li key={`${index}-${assumption}`}>{assumption}</li>
              ))}
            </Stack>
          </AdvancedSection>
        </Stack>
      ) : null}
    </Stack>
  );
}
