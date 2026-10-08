import {
  Alert,
  Box,
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
import { Link } from '@tanstack/react-router';
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
import { useHousehold } from '../households/HouseholdContext';
import { localCalendarDate } from '../people/localDate';
import { PurchasePlanDetailDialog } from './PurchasePlanDetailDialog';

type Access = components['schemas']['HouseholdAccessRead'];
type Lookup = components['schemas']['LookupRead'];
type Plan = components['schemas']['PurchasePlanRead'];
type Provider = components['schemas']['PurchaseProviderRead'];
type Draft = Record<
  | 'buffer'
  | 'currency'
  | 'displayName'
  | 'intendedUse'
  | 'location'
  | 'maxLvr'
  | 'minimumSurplus'
  | 'notes'
  | 'priceMax'
  | 'priceMin'
  | 'providerCode'
  | 'providerSettings'
  | 'purchaseTypeId'
  | 'targetDate',
  string
>;

const blank = (currency: string): Draft => ({
  buffer: '0',
  currency,
  displayName: '',
  intendedUse: 'Owner occupied',
  location: '',
  maxLvr: '',
  minimumSurplus: '',
  notes: '',
  priceMax: '',
  priceMin: '',
  providerCode: '',
  providerSettings: '{}',
  purchaseTypeId: '',
  targetDate: localCalendarDate(),
});
const moneyPattern = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const message = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed';
const cents = (value: string) => {
  const [whole, fraction = ''] = value.split('.');
  return BigInt(`${whole}${fraction.padEnd(2, '0')}`);
};

function PlanDialog({
  currency,
  householdId,
  onClose,
  providers,
  purchaseTypes,
}: {
  currency: string;
  householdId: string;
  onClose: () => void;
  providers: Provider[];
  purchaseTypes: Lookup[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [form, setForm] = useState(() => blank(currency));
  const [validation, setValidation] = useState('');
  const field =
    (key: keyof Draft) => (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));
  const save = useMutation({
    mutationFn: (body: components['schemas']['PurchasePlanCreate']) =>
      apiRequest<Plan>(`/api/v1/households/${householdId}/purchase-plans`, {
        body: JSON.stringify(body),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['purchase-plans', householdId],
      });
      notification.notify('Purchase plan saved.', 'success');
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    if (
      !form.displayName.trim() ||
      !form.purchaseTypeId ||
      !form.intendedUse.trim()
    )
      return setValidation(
        'Name, purchase type and intended use are required.',
      );
    const amounts = [form.priceMin, form.priceMax, form.buffer];
    if (form.minimumSurplus) amounts.push(form.minimumSurplus);
    if (
      amounts.some((value) => !moneyPattern.test(value)) ||
      cents(form.priceMax) < cents(form.priceMin)
    )
      return setValidation(
        'Enter non-negative monetary amounts with no more than two decimal places; the maximum price must be at least the minimum.',
      );
    if (
      form.maxLvr &&
      (!/^\d{1,3}(?:\.\d{1,4})?$/.test(form.maxLvr) ||
        Number(form.maxLvr) > 100)
    )
      return setValidation(
        'Maximum LVR must be between 0 and 100 with no more than four decimal places.',
      );
    let settings: Record<string, unknown>;
    try {
      const parsed = JSON.parse(form.providerSettings) as unknown;
      if (
        typeof parsed !== 'object' ||
        parsed === null ||
        Array.isArray(parsed)
      )
        throw new Error();
      settings = parsed as Record<string, unknown>;
    } catch {
      return setValidation('Provider settings must be a valid JSON object.');
    }
    save.mutate({
      costs: [],
      currency: form.currency.toUpperCase(),
      desired_buffer: form.buffer,
      display_name: form.displayName.trim(),
      funding_sources: [],
      intended_use: form.intendedUse.trim(),
      max_lvr: form.maxLvr || null,
      minimum_monthly_surplus: form.minimumSurplus || null,
      notes: form.notes || null,
      ownership: [],
      provider_code: form.providerCode || null,
      provider_settings: form.providerCode ? settings : {},
      purchase_type_id: form.purchaseTypeId,
      target_date: form.targetDate,
      target_location: form.location.trim()
        ? { description: form.location.trim() }
        : {},
      target_price_max: form.priceMax,
      target_price_min: form.priceMin,
    });
  };
  return (
    <Dialog
      fullWidth
      maxWidth="md"
      onClose={save.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Add purchase plan</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Plan name"
              onChange={field('displayName')}
              required
              value={form.displayName}
            />
            <TextField
              fullWidth
              label="Purchase type"
              onChange={field('purchaseTypeId')}
              required
              select
              value={form.purchaseTypeId}
            >
              {purchaseTypes.map((item) => (
                <MenuItem key={item.id} value={item.id}>
                  {item.display_name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              fullWidth
              label="Target date"
              onChange={field('targetDate')}
              type="date"
              value={form.targetDate}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Intended use"
              onChange={field('intendedUse')}
              value={form.intendedUse}
            />
            <TextField
              fullWidth
              label="Target location"
              onChange={field('location')}
              value={form.location}
            />
            <TextField
              label="Currency"
              onChange={field('currency')}
              slotProps={{ htmlInput: { maxLength: 3 } }}
              value={form.currency}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label={`Minimum price (${form.currency})`}
              onChange={field('priceMin')}
              value={form.priceMin}
            />
            <TextField
              fullWidth
              label={`Maximum price (${form.currency})`}
              onChange={field('priceMax')}
              value={form.priceMax}
            />
            <TextField
              fullWidth
              label={`Desired buffer (${form.currency})`}
              onChange={field('buffer')}
              value={form.buffer}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Maximum LVR (%)"
              onChange={field('maxLvr')}
              value={form.maxLvr}
            />
            <TextField
              fullWidth
              label={`Minimum monthly surplus (${form.currency})`}
              onChange={field('minimumSurplus')}
              value={form.minimumSurplus}
            />
          </Stack>
          <TextField
            label="Notes"
            multiline
            minRows={2}
            onChange={field('notes')}
            value={form.notes}
          />
          <Alert severity="info">
            Save the plan first, then open its details to add funding sources,
            costs and proposed ownership.
          </Alert>
          <AdvancedSection description="Installed providers can estimate jurisdiction-specific purchase costs. Their settings remain optional and country-neutral.">
            <Stack spacing={2}>
              <TextField
                label="Purchase cost provider"
                onChange={field('providerCode')}
                select
                value={form.providerCode}
              >
                <MenuItem value="">No provider</MenuItem>
                {providers.map((provider) => (
                  <MenuItem key={provider.code} value={provider.code}>
                    {provider.display_name}
                  </MenuItem>
                ))}
              </TextField>
              {form.providerCode ? (
                <TextField
                  label="Provider settings (JSON)"
                  multiline
                  minRows={3}
                  onChange={field('providerSettings')}
                  value={form.providerSettings}
                />
              ) : null}
            </Stack>
          </AdvancedSection>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {save.error ? (
            <Alert severity="error">
              Purchase plan could not be saved. {message(save.error)}
            </Alert>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={save.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button disabled={save.isPending} onClick={submit} variant="contained">
          Save plan
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function PurchasesPage() {
  const household = useHousehold();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const householdId = household.selected?.id ?? null;
  const plans = useQuery({
    enabled: householdId !== null,
    queryFn: () =>
      apiRequest<Plan[]>(`/api/v1/households/${householdId}/purchase-plans`),
    queryKey: ['purchase-plans', householdId],
    retry: false,
  });
  const purchaseTypes = useQuery({
    enabled: householdId !== null,
    queryFn: () => apiRequest<Lookup[]>('/api/v1/lookups/purchase_type'),
    queryKey: ['lookups', 'purchase_type'],
    retry: false,
  });
  const providers = useQuery({
    enabled: householdId !== null,
    queryFn: () => apiRequest<Provider[]>('/api/v1/purchase-providers'),
    queryKey: ['purchase-providers'],
    retry: false,
  });
  const access = useQuery({
    enabled: householdId !== null,
    queryFn: () =>
      apiRequest<Access>(`/api/v1/households/${householdId}/access`),
    queryKey: ['household-access', householdId],
    retry: false,
  });
  if (!household.selected)
    return (
      <Stack spacing={3}>
        <Typography component="h1" variant="h4">
          Purchase plans
        </Typography>
        <EmptyState
          description="Select a household before planning a future property purchase."
          title="No household selected"
        />
        <Button
          component={Link}
          sx={{ alignSelf: 'flex-start' }}
          to="/households"
          variant="contained"
        >
          Choose a household
        </Button>
      </Stack>
    );
  const selected = household.selected;
  const loading =
    plans.isPending ||
    access.isPending ||
    purchaseTypes.isPending ||
    providers.isPending;
  const failed =
    plans.error ?? access.error ?? purchaseTypes.error ?? providers.error;
  const columns: DataColumn<Plan>[] = [
    { key: 'name', label: 'Plan', render: (row) => row.display_name },
    {
      key: 'type',
      label: 'Purchase type',
      render: (row) =>
        purchaseTypes.data?.find((item) => item.id === row.purchase_type_id)
          ?.display_name ?? 'Unavailable type',
    },
    {
      key: 'price',
      label: 'Target price',
      render: (row) =>
        `${formatCurrency(row.target_price_min, row.currency)} – ${formatCurrency(row.target_price_max, row.currency)}`,
    },
    {
      key: 'date',
      label: 'Target date',
      render: (row) => formatDate(row.target_date),
    },
    { key: 'use', label: 'Intended use', render: (row) => row.intended_use },
    {
      key: 'provider',
      label: 'Cost provider',
      render: (row) =>
        providers.data?.find((item) => item.code === row.provider_code)
          ?.display_name ??
        (row.provider_code ? 'Provider unavailable' : 'None'),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) => (
        <Button onClick={() => setSelectedPlanId(row.id)}>View details</Button>
      ),
    },
  ];
  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Purchase plans
        </Typography>
        <Typography color="text.secondary">
          Explore a possible property purchase without changing{' '}
          {selected.display_name}&apos;s recorded position.
        </Typography>
      </Box>
      {loading ? (
        <CircularProgress aria-label="Loading purchase plans" />
      ) : failed ? (
        <Alert severity="error">
          Purchase plans could not be loaded. {message(failed)}
        </Alert>
      ) : (
        <>
          {access.data?.can_edit ? (
            <Button
              onClick={() => setCreateOpen(true)}
              sx={{ alignSelf: 'flex-start' }}
              variant="contained"
            >
              Add purchase plan
            </Button>
          ) : (
            <Alert severity="info">
              You have view-only access to purchase plans.
            </Alert>
          )}
          {plans.data?.length ? (
            <DataTable
              caption="Purchase plans"
              columns={columns}
              getRowKey={(row) => row.id}
              rows={plans.data}
            />
          ) : (
            <EmptyState
              description={
                access.data?.can_edit
                  ? 'Add a plan to record a target and comfort limits.'
                  : 'No purchase plans have been added by a household editor yet.'
              }
              title="No purchase plans yet"
            />
          )}
        </>
      )}
      {createOpen && purchaseTypes.data && providers.data ? (
        <PlanDialog
          currency={selected.currency}
          householdId={selected.id}
          onClose={() => setCreateOpen(false)}
          providers={providers.data}
          purchaseTypes={purchaseTypes.data}
        />
      ) : null}
      {selectedPlanId && access.data ? (
        <PurchasePlanDetailDialog
          canEdit={access.data.can_edit}
          householdId={selected.id}
          onClose={() => setSelectedPlanId(null)}
          planId={selectedPlanId}
        />
      ) : null}
    </Stack>
  );
}
