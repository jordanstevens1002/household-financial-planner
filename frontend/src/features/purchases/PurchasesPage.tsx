import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
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

type Access = components['schemas']['HouseholdAccessRead'];
type Lookup = components['schemas']['LookupRead'];
type Person = components['schemas']['PersonRead'];
type Plan = components['schemas']['PurchasePlanRead'];
type Provider = components['schemas']['PurchaseProviderRead'];

interface FundingDraft {
  amount: string;
  availableDate: string;
  displayName: string;
  isBorrowed: boolean;
  sourceType: string;
}

interface CostDraft {
  amount: string;
  displayName: string;
  isEstimate: boolean;
}

interface OwnerDraft {
  externalName: string;
  ownerType: 'HOUSEHOLD' | 'PERSON' | 'EXTERNAL_PARTY';
  percentage: string;
  personId: string;
}

interface FormDraft {
  buffer: string;
  currency: string;
  displayName: string;
  intendedUse: string;
  location: string;
  maxLvr: string;
  minimumSurplus: string;
  notes: string;
  priceMax: string;
  priceMin: string;
  providerCode: string;
  providerSettings: string;
  purchaseTypeId: string;
  targetDate: string;
}

const emptyForm = (currency: string): FormDraft => ({
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The request failed';
}

function PurchasePlanDialog({
  currency,
  householdId,
  onClose,
  people,
  providers,
  purchaseTypes,
}: {
  currency: string;
  householdId: string;
  onClose: () => void;
  people: Person[];
  providers: Provider[];
  purchaseTypes: Lookup[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notify = useNotification();
  const [form, setForm] = useState(() => emptyForm(currency));
  const [funding, setFunding] = useState<FundingDraft[]>([]);
  const [costs, setCosts] = useState<CostDraft[]>([]);
  const [owners, setOwners] = useState<OwnerDraft[]>([]);
  const [validation, setValidation] = useState('');
  const setField = (field: keyof FormDraft, value: string) =>
    setForm((current) => ({ ...current, [field]: value }));
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
      notify.notify('Purchase plan saved.', 'success');
      onClose();
    },
  });
  const submit = () => {
    setValidation('');
    const min = Number(form.priceMin);
    const max = Number(form.priceMax);
    if (
      !form.displayName.trim() ||
      !form.purchaseTypeId ||
      !form.intendedUse.trim()
    ) {
      setValidation('Name, purchase type and intended use are required.');
      return;
    }
    if (
      !Number.isFinite(min) ||
      !Number.isFinite(max) ||
      min < 0 ||
      max < min
    ) {
      setValidation(
        'Enter a valid price range; the maximum must be at least the minimum.',
      );
      return;
    }
    const ownershipTotal = owners.reduce(
      (total, owner) => total + Number(owner.percentage),
      0,
    );
    if (owners.length > 0 && ownershipTotal !== 100) {
      setValidation('Proposed ownership must total exactly 100%.');
      return;
    }
    let providerSettings: Record<string, unknown>;
    let targetLocation: Record<string, unknown>;
    try {
      providerSettings = JSON.parse(form.providerSettings) as Record<
        string,
        unknown
      >;
      targetLocation = form.location.trim()
        ? { description: form.location.trim() }
        : {};
    } catch {
      setValidation('Provider settings must be a valid JSON object.');
      return;
    }
    save.mutate({
      costs: costs.map((cost, index) => ({
        amount: cost.amount,
        code: `USER_${index + 1}`,
        display_name: cost.displayName,
        is_estimate: cost.isEstimate,
      })),
      currency: form.currency.toUpperCase(),
      desired_buffer: form.buffer || '0',
      display_name: form.displayName.trim(),
      funding_sources: funding.map((source) => ({
        amount: source.amount,
        available_date: source.availableDate,
        display_name: source.displayName,
        is_borrowed: source.isBorrowed,
        notes: null,
        source_type: source.sourceType,
      })),
      intended_use: form.intendedUse.trim(),
      max_lvr: form.maxLvr || null,
      minimum_monthly_surplus: form.minimumSurplus || null,
      notes: form.notes || null,
      ownership: owners.map((owner) => ({
        external_owner_name:
          owner.ownerType === 'EXTERNAL_PARTY' ? owner.externalName : null,
        owner_type: owner.ownerType,
        ownership_percentage: owner.percentage,
        person_id: owner.ownerType === 'PERSON' ? owner.personId : null,
      })),
      provider_code: form.providerCode || null,
      provider_settings: form.providerCode ? providerSettings : {},
      purchase_type_id: form.purchaseTypeId,
      target_date: form.targetDate,
      target_location: targetLocation,
      target_price_max: form.priceMax,
      target_price_min: form.priceMin,
    });
  };

  return (
    <Dialog
      fullWidth
      maxWidth="lg"
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
              onChange={(e) => setField('displayName', e.target.value)}
              required
              value={form.displayName}
            />
            <TextField
              fullWidth
              label="Purchase type"
              onChange={(e) => setField('purchaseTypeId', e.target.value)}
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
              onChange={(e) => setField('targetDate', e.target.value)}
              type="date"
              value={form.targetDate}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Intended use"
              onChange={(e) => setField('intendedUse', e.target.value)}
              value={form.intendedUse}
            />
            <TextField
              fullWidth
              label="Target location"
              onChange={(e) => setField('location', e.target.value)}
              value={form.location}
            />
            <TextField
              label="Currency"
              onChange={(e) => setField('currency', e.target.value)}
              slotProps={{ htmlInput: { maxLength: 3 } }}
              value={form.currency}
            />
          </Stack>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label={`Minimum price (${form.currency})`}
              onChange={(e) => setField('priceMin', e.target.value)}
              value={form.priceMin}
            />
            <TextField
              fullWidth
              label={`Maximum price (${form.currency})`}
              onChange={(e) => setField('priceMax', e.target.value)}
              value={form.priceMax}
            />
            <TextField
              fullWidth
              label={`Desired buffer (${form.currency})`}
              onChange={(e) => setField('buffer', e.target.value)}
              value={form.buffer}
            />
          </Stack>

          <Typography variant="h3">Funding sources</Typography>
          {funding.map((source, index) => (
            <Stack
              direction={{ md: 'row', xs: 'column' }}
              key={index}
              spacing={1}
            >
              <TextField
                label="Name"
                onChange={(e) =>
                  setFunding((rows) =>
                    rows.map((row, i) =>
                      i === index
                        ? { ...row, displayName: e.target.value }
                        : row,
                    ),
                  )
                }
                value={source.displayName}
              />
              <TextField
                label="Type"
                onChange={(e) =>
                  setFunding((rows) =>
                    rows.map((row, i) =>
                      i === index
                        ? { ...row, sourceType: e.target.value }
                        : row,
                    ),
                  )
                }
                value={source.sourceType}
              />
              <TextField
                label="Amount"
                onChange={(e) =>
                  setFunding((rows) =>
                    rows.map((row, i) =>
                      i === index ? { ...row, amount: e.target.value } : row,
                    ),
                  )
                }
                value={source.amount}
              />
              <TextField
                label="Available"
                onChange={(e) =>
                  setFunding((rows) =>
                    rows.map((row, i) =>
                      i === index
                        ? { ...row, availableDate: e.target.value }
                        : row,
                    ),
                  )
                }
                type="date"
                value={source.availableDate}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={source.isBorrowed}
                    onChange={(e) =>
                      setFunding((rows) =>
                        rows.map((row, i) =>
                          i === index
                            ? { ...row, isBorrowed: e.target.checked }
                            : row,
                        ),
                      )
                    }
                  />
                }
                label="Borrowed"
              />
              <Button
                color="error"
                onClick={() =>
                  setFunding((rows) => rows.filter((_, i) => i !== index))
                }
              >
                Remove
              </Button>
            </Stack>
          ))}
          <Button
            onClick={() =>
              setFunding((rows) => [
                ...rows,
                {
                  amount: '',
                  availableDate: form.targetDate,
                  displayName: '',
                  isBorrowed: false,
                  sourceType: 'SAVINGS',
                },
              ])
            }
            sx={{ alignSelf: 'flex-start' }}
          >
            Add funding source
          </Button>

          <Typography variant="h3">User costs</Typography>
          {costs.map((cost, index) => (
            <Stack direction="row" key={index} spacing={1}>
              <TextField
                fullWidth
                label="Cost name"
                onChange={(e) =>
                  setCosts((rows) =>
                    rows.map((row, i) =>
                      i === index
                        ? { ...row, displayName: e.target.value }
                        : row,
                    ),
                  )
                }
                value={cost.displayName}
              />
              <TextField
                fullWidth
                label="Amount"
                onChange={(e) =>
                  setCosts((rows) =>
                    rows.map((row, i) =>
                      i === index ? { ...row, amount: e.target.value } : row,
                    ),
                  )
                }
                value={cost.amount}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={cost.isEstimate}
                    onChange={(e) =>
                      setCosts((rows) =>
                        rows.map((row, i) =>
                          i === index
                            ? { ...row, isEstimate: e.target.checked }
                            : row,
                        ),
                      )
                    }
                  />
                }
                label="Estimate"
              />
              <Button
                color="error"
                onClick={() =>
                  setCosts((rows) => rows.filter((_, i) => i !== index))
                }
              >
                Remove
              </Button>
            </Stack>
          ))}
          <Button
            onClick={() =>
              setCosts((rows) => [
                ...rows,
                { amount: '', displayName: '', isEstimate: true },
              ])
            }
            sx={{ alignSelf: 'flex-start' }}
          >
            Add user cost
          </Button>

          <Typography variant="h3">Proposed ownership</Typography>
          {owners.map((owner, index) => (
            <Stack
              direction={{ md: 'row', xs: 'column' }}
              key={index}
              spacing={1}
            >
              <TextField
                label="Owner"
                onChange={(e) =>
                  setOwners((rows) =>
                    rows.map((row, i) =>
                      i === index
                        ? {
                            ...row,
                            ownerType: e.target
                              .value as OwnerDraft['ownerType'],
                          }
                        : row,
                    ),
                  )
                }
                select
                value={owner.ownerType}
              >
                <MenuItem value="HOUSEHOLD">Household jointly</MenuItem>
                <MenuItem value="PERSON">A person in this household</MenuItem>
                <MenuItem value="EXTERNAL_PARTY">Someone else</MenuItem>
              </TextField>
              {owner.ownerType === 'PERSON' ? (
                <TextField
                  label="Person"
                  onChange={(e) =>
                    setOwners((rows) =>
                      rows.map((row, i) =>
                        i === index
                          ? { ...row, personId: e.target.value }
                          : row,
                      ),
                    )
                  }
                  select
                  value={owner.personId}
                >
                  {people.map((person) => (
                    <MenuItem key={person.id} value={person.id}>
                      {person.display_name}
                    </MenuItem>
                  ))}
                </TextField>
              ) : null}
              {owner.ownerType === 'EXTERNAL_PARTY' ? (
                <TextField
                  label="Owner name"
                  onChange={(e) =>
                    setOwners((rows) =>
                      rows.map((row, i) =>
                        i === index
                          ? { ...row, externalName: e.target.value }
                          : row,
                      ),
                    )
                  }
                  value={owner.externalName}
                />
              ) : null}
              <TextField
                label="Share (%)"
                onChange={(e) =>
                  setOwners((rows) =>
                    rows.map((row, i) =>
                      i === index
                        ? { ...row, percentage: e.target.value }
                        : row,
                    ),
                  )
                }
                value={owner.percentage}
              />
              <Button
                color="error"
                onClick={() =>
                  setOwners((rows) => rows.filter((_, i) => i !== index))
                }
              >
                Remove
              </Button>
            </Stack>
          ))}
          <Button
            onClick={() =>
              setOwners((rows) => [
                ...rows,
                {
                  externalName: '',
                  ownerType: 'HOUSEHOLD',
                  percentage: '',
                  personId: '',
                },
              ])
            }
            sx={{ alignSelf: 'flex-start' }}
          >
            Add proposed owner
          </Button>

          <Stack direction={{ md: 'row', xs: 'column' }} spacing={2}>
            <TextField
              fullWidth
              label="Maximum LVR (%)"
              onChange={(e) => setField('maxLvr', e.target.value)}
              value={form.maxLvr}
            />
            <TextField
              fullWidth
              label={`Minimum monthly surplus (${form.currency})`}
              onChange={(e) => setField('minimumSurplus', e.target.value)}
              value={form.minimumSurplus}
            />
          </Stack>
          <TextField
            label="Notes"
            multiline
            minRows={2}
            onChange={(e) => setField('notes', e.target.value)}
            value={form.notes}
          />
          <AdvancedSection description="Installed providers can estimate jurisdiction-specific purchase costs. Their settings remain optional and country-neutral.">
            <Stack spacing={2}>
              <TextField
                label="Purchase cost provider"
                onChange={(e) => setField('providerCode', e.target.value)}
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
                  onChange={(e) => setField('providerSettings', e.target.value)}
                  value={form.providerSettings}
                />
              ) : null}
            </Stack>
          </AdvancedSection>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {save.error ? (
            <Alert severity="error">
              Purchase plan could not be saved. {errorMessage(save.error)}
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
  const people = useQuery({
    enabled: householdId !== null,
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
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
          actionLabel="Choose a household"
          description="Select a household before planning a future property purchase."
          onAction={undefined}
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
  const selectedHousehold = household.selected;
  const loading =
    plans.isPending ||
    access.isPending ||
    purchaseTypes.isPending ||
    providers.isPending ||
    people.isPending;
  const failed =
    plans.error ??
    access.error ??
    purchaseTypes.error ??
    providers.error ??
    people.error;
  const typeName = (id: string) =>
    purchaseTypes.data?.find((item) => item.id === id)?.display_name ??
    'Unavailable type';
  const columns: DataColumn<Plan>[] = [
    { key: 'name', label: 'Plan', render: (row) => row.display_name },
    {
      key: 'type',
      label: 'Purchase type',
      render: (row) => typeName(row.purchase_type_id),
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
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Purchase plans
        </Typography>
        <Typography color="text.secondary">
          Explore a possible property purchase without changing{' '}
          {selectedHousehold.display_name}&apos;s recorded position.
        </Typography>
      </Box>
      {loading ? (
        <CircularProgress aria-label="Loading purchase plans" />
      ) : failed ? (
        <Alert severity="error">
          Purchase plans could not be loaded. {errorMessage(failed)}
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
                  ? 'Add a plan to record a target, possible funding and comfort limits.'
                  : 'No purchase plans have been added by a household editor yet.'
              }
              title="No purchase plans yet"
            />
          )}
        </>
      )}
      {createOpen && purchaseTypes.data && providers.data && people.data ? (
        <PurchasePlanDialog
          currency={selectedHousehold.currency}
          householdId={selectedHousehold.id}
          onClose={() => setCreateOpen(false)}
          people={people.data}
          providers={providers.data}
          purchaseTypes={purchaseTypes.data}
        />
      ) : null}
    </Stack>
  );
}
