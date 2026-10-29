import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { AdvancedSection } from '../../shared/AdvancedSection';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { localCalendarDate } from '../people/localDate';

type Account = components['schemas']['RetirementAccountRead'];
type Contribution = components['schemas']['ContributionProfileRead'];
type Event = components['schemas']['RetirementEventRead'];

const unsignedMoney = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const signedMoney = /^-?(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const percentage = /^(?:100(?:\.0{1,4})?|\d{1,2}(?:\.\d{1,4})?)$/;
const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed';

function ContributionDialog({
  account,
  onClose,
}: {
  account: Account;
  onClose: () => void;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [effectiveFrom, setEffectiveFrom] = useState(localCalendarDate());
  const [effectiveTo, setEffectiveTo] = useState('');
  const [employerRate, setEmployerRate] = useState('');
  const [employerAmount, setEmployerAmount] = useState('');
  const [preTax, setPreTax] = useState('0');
  const [postTax, setPostTax] = useState('0');
  const [taxRate, setTaxRate] = useState('0');
  const [annualCap, setAnnualCap] = useState('');
  const [validation, setValidation] = useState('');
  const save = useMutation({
    mutationFn: (body: components['schemas']['ContributionProfileCreate']) =>
      apiRequest<Contribution>(
        `/api/v1/retirement-accounts/${account.id}/contribution-profiles`,
        {
          body: JSON.stringify(body),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['retirement-contributions', account.id],
      });
      notification.notify('Contribution profile saved.', 'success');
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    if (!effectiveFrom)
      return setValidation('An effective-from date is required.');
    if (effectiveTo && effectiveTo < effectiveFrom)
      return setValidation('Effective to cannot precede effective from.');
    if (employerRate && employerAmount)
      return setValidation('Use an employer rate or amount, not both.');
    if (employerRate && !percentage.test(employerRate))
      return setValidation('Employer rate must be from 0 to 100.');
    if (
      [employerAmount, preTax, postTax, annualCap].some(
        (value) => value && !unsignedMoney.test(value),
      )
    )
      return setValidation(
        'Contribution amounts require at most 16 whole digits and two decimals.',
      );
    if (!percentage.test(taxRate))
      return setValidation('Contribution tax rate must be from 0 to 100.');
    save.mutate({
      annual_pre_tax_cap: annualCap || null,
      contribution_tax_rate: taxRate,
      effective_from: effectiveFrom,
      effective_to: effectiveTo || null,
      employer_amount: employerAmount || null,
      employer_rate: employerRate || null,
      voluntary_post_tax_amount: postTax,
      voluntary_pre_tax_amount: preTax,
    });
  };
  return (
    <Dialog
      fullWidth
      maxWidth="md"
      onClose={save.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Add contribution profile</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="info">
            Profiles cannot overlap. Set an end date for a finite arrangement;
            an ongoing profile prevents another profile from being added.
          </Alert>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
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
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Employer contribution rate (%)"
              onChange={(event) => setEmployerRate(event.target.value)}
              value={employerRate}
            />
            <TextField
              fullWidth
              label={`Employer annual amount (${account.currency})`}
              onChange={(event) => setEmployerAmount(event.target.value)}
              value={employerAmount}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label={`Voluntary pre-tax annual amount (${account.currency})`}
              onChange={(event) => setPreTax(event.target.value)}
              value={preTax}
            />
            <TextField
              fullWidth
              label={`Voluntary post-tax annual amount (${account.currency})`}
              onChange={(event) => setPostTax(event.target.value)}
              value={postTax}
            />
          </Stack>
          <AdvancedSection description="Tax and cap assumptions are optional planning inputs and are not country defaults.">
            <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
              <TextField
                fullWidth
                label="Contribution tax rate (%)"
                onChange={(event) => setTaxRate(event.target.value)}
                value={taxRate}
              />
              <TextField
                fullWidth
                label={`Annual pre-tax cap (${account.currency}, optional)`}
                onChange={(event) => setAnnualCap(event.target.value)}
                value={annualCap}
              />
            </Stack>
          </AdvancedSection>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {save.error ? (
            <Alert severity="error">
              Profile could not be saved. {message(save.error)}
            </Alert>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={save.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={save.isPending} onClick={submit} variant="contained">
          Save profile
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function AdjustmentDialog({
  account,
  onClose,
}: {
  account: Account;
  onClose: () => void;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [effectiveDate, setEffectiveDate] = useState(localCalendarDate());
  const [amount, setAmount] = useState('');
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const [notes, setNotes] = useState('');
  const [validation, setValidation] = useState('');
  const save = useMutation({
    mutationFn: (body: components['schemas']['RetirementEventCreate']) =>
      apiRequest<Event>(`/api/v1/retirement-accounts/${account.id}/events`, {
        body: JSON.stringify(body),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['retirement-adjustments', account.id],
      });
      notification.notify('Balance adjustment saved.', 'success');
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    if (!effectiveDate) return setValidation('An effective date is required.');
    if (!signedMoney.test(amount) || Number(amount) === 0)
      return setValidation(
        'Enter a non-zero amount with at most 16 whole digits and two decimals.',
      );
    if (idempotencyKey.trim().length > 100)
      return setValidation('Idempotency key cannot exceed 100 characters.');
    if (notes.length > 2000)
      return setValidation('Notes cannot exceed 2,000 characters.');
    save.mutate({
      amount,
      effective_date: effectiveDate,
      event_type: 'BALANCE_ADJUSTMENT',
      idempotency_key: idempotencyKey.trim() || null,
      notes: notes.trim() || null,
    });
  };
  return (
    <Dialog
      fullWidth
      maxWidth="sm"
      onClose={save.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Add balance adjustment</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Alert severity="info">
            Use a positive amount for money added outside contribution profiles
            and a negative amount for a withdrawal or correction.
          </Alert>
          <TextField
            label="Effective date"
            onChange={(event) => setEffectiveDate(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            type="date"
            value={effectiveDate}
          />
          <TextField
            label={`Adjustment amount (${account.currency})`}
            onChange={(event) => setAmount(event.target.value)}
            value={amount}
          />
          <AdvancedSection description="Optional deduplication and notes.">
            <Stack spacing={2}>
              <TextField
                label="Idempotency key (optional)"
                onChange={(event) => setIdempotencyKey(event.target.value)}
                value={idempotencyKey}
              />
              <TextField
                label="Notes (optional)"
                minRows={2}
                multiline
                onChange={(event) => setNotes(event.target.value)}
                value={notes}
              />
            </Stack>
          </AdvancedSection>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {save.error ? (
            <Alert severity="error">
              Adjustment could not be saved. {message(save.error)}
            </Alert>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={save.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={save.isPending} onClick={submit} variant="contained">
          Save adjustment
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function RetirementActivityDialog({
  account,
  canEdit,
  onClose,
}: {
  account: Account;
  canEdit: boolean;
  onClose: () => void;
}) {
  const [addingContribution, setAddingContribution] = useState(false);
  const [addingAdjustment, setAddingAdjustment] = useState(false);
  const contributions = useQuery({
    queryFn: () =>
      apiRequest<Contribution[]>(
        `/api/v1/retirement-accounts/${account.id}/contribution-profiles`,
      ),
    queryKey: ['retirement-contributions', account.id],
    retry: false,
  });
  const adjustments = useQuery({
    queryFn: () =>
      apiRequest<Event[]>(`/api/v1/retirement-accounts/${account.id}/events`),
    queryKey: ['retirement-adjustments', account.id],
    retry: false,
  });
  const contributionColumns: DataColumn<Contribution>[] = [
    {
      key: 'dates',
      label: 'Effective dates',
      render: (item) =>
        `${formatDate(item.effective_from)} – ${item.effective_to ? formatDate(item.effective_to) : 'Ongoing'}`,
    },
    {
      key: 'employer',
      label: 'Employer',
      render: (item) =>
        item.employer_rate != null
          ? `${item.employer_rate}%`
          : item.employer_amount != null
            ? `${formatCurrency(item.employer_amount, account.currency)} yearly`
            : 'None',
    },
    {
      key: 'pre-tax',
      label: 'Voluntary pre-tax',
      render: (item) =>
        formatCurrency(item.voluntary_pre_tax_amount, account.currency),
    },
    {
      key: 'post-tax',
      label: 'Voluntary post-tax',
      render: (item) =>
        formatCurrency(item.voluntary_post_tax_amount, account.currency),
    },
    {
      key: 'tax',
      label: 'Tax rate',
      render: (item) => `${item.contribution_tax_rate}%`,
    },
  ];
  const adjustmentColumns: DataColumn<Event>[] = [
    {
      key: 'date',
      label: 'Effective date',
      render: (item) => formatDate(item.effective_date),
    },
    {
      key: 'amount',
      label: 'Amount',
      render: (item) => formatCurrency(item.amount, account.currency),
    },
  ];
  const adjustmentMetadataColumns: DataColumn<Event>[] = [
    {
      key: 'date',
      label: 'Effective date',
      render: (item) => formatDate(item.effective_date),
    },
    {
      key: 'idempotency',
      label: 'Idempotency key',
      render: (item) => item.idempotency_key || '—',
    },
    { key: 'notes', label: 'Notes', render: (item) => item.notes || '—' },
  ];
  return (
    <Dialog fullWidth maxWidth="lg" onClose={onClose} open>
      <DialogTitle>
        {account.display_name} — contributions and adjustments
      </DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ pt: 1 }}>
          {!account.is_active ? (
            <Alert severity="warning">
              This account is inactive. Its history remains available, but it
              must be reactivated before a new profile can be added.
            </Alert>
          ) : null}
          <Box>
            <Stack
              direction="row"
              sx={{ justifyContent: 'space-between', mb: 1 }}
            >
              <Typography component="h3" variant="h6">
                Contribution profiles
              </Typography>
              {canEdit ? (
                <Button
                  disabled={!account.is_active}
                  onClick={() => setAddingContribution(true)}
                >
                  Add profile
                </Button>
              ) : null}
            </Stack>
            {contributions.isPending ? (
              <CircularProgress aria-label="Loading contribution profiles" />
            ) : contributions.error ? (
              <Alert
                action={
                  <Button onClick={() => void contributions.refetch()}>
                    Retry
                  </Button>
                }
                severity="error"
              >
                Contribution profiles could not be loaded.{' '}
                {message(contributions.error)}
              </Alert>
            ) : contributions.data.length ? (
              <DataTable
                caption="Contribution profile history"
                columns={contributionColumns}
                getRowKey={(item) => item.id}
                rows={contributions.data}
              />
            ) : (
              <EmptyState
                description="Add a dated profile to describe employer and voluntary contributions."
                title="No contribution profiles"
              />
            )}
          </Box>
          <Box>
            <Stack
              direction="row"
              sx={{ justifyContent: 'space-between', mb: 1 }}
            >
              <Typography component="h3" variant="h6">
                Balance adjustments
              </Typography>
              {canEdit ? (
                <Button
                  disabled={!account.is_active}
                  onClick={() => setAddingAdjustment(true)}
                >
                  Add adjustment
                </Button>
              ) : null}
            </Stack>
            {adjustments.isPending ? (
              <CircularProgress aria-label="Loading balance adjustments" />
            ) : adjustments.error ? (
              <Alert
                action={
                  <Button onClick={() => void adjustments.refetch()}>
                    Retry
                  </Button>
                }
                severity="error"
              >
                Balance adjustments could not be loaded.{' '}
                {message(adjustments.error)}
              </Alert>
            ) : adjustments.data.length ? (
              <Stack spacing={2}>
                <DataTable
                  caption="Balance adjustment history"
                  columns={adjustmentColumns}
                  getRowKey={(item) => item.id}
                  rows={adjustments.data}
                />
                <AdvancedSection description="Optional adjustment identifiers and notes.">
                  <DataTable
                    caption="Balance adjustment metadata"
                    columns={adjustmentMetadataColumns}
                    getRowKey={(item) => item.id}
                    rows={adjustments.data}
                  />
                </AdvancedSection>
              </Stack>
            ) : (
              <EmptyState
                description="Record a dated deposit, withdrawal or balance correction outside regular contributions."
                title="No balance adjustments"
              />
            )}
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
      {addingContribution ? (
        <ContributionDialog
          account={account}
          onClose={() => setAddingContribution(false)}
        />
      ) : null}
      {addingAdjustment ? (
        <AdjustmentDialog
          account={account}
          onClose={() => setAddingAdjustment(false)}
        />
      ) : null}
    </Dialog>
  );
}
