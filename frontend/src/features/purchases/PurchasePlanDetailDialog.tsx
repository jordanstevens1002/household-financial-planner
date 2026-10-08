import {
  Alert,
  Button,
  Checkbox,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { formatCurrency, formatDate } from '../../shared/format';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { PurchaseFeasibilityPanel } from './PurchaseFeasibilityPanel';

type Detail = components['schemas']['PurchasePlanDetail'];
type Funding = components['schemas']['FundingSourceRead'];
type Cost = components['schemas']['CostRead'];
type Owner = components['schemas']['PurchaseOwnershipRead'];
type Person = components['schemas']['PersonRead'];
type OwnerType = components['schemas']['OwnerType'];

const moneyPattern = /^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/;
const percentagePattern = /^(?:100(?:\.0{1,4})?|\d{1,2}(?:\.\d{1,4})?)$/;
const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed';
const scaledPercentage = (value: string) => {
  const [whole, fraction = ''] = value.split('.');
  return BigInt(`${whole}${fraction.padEnd(4, '0')}`);
};

interface ChildDraft {
  amount: string;
  availableDate: string;
  code: string;
  displayName: string;
  isBorrowed: boolean;
  isEstimate: boolean;
  notes: string;
  sourceType: string;
}

const childDraft = (item?: Funding | Cost): ChildDraft => ({
  amount: item?.amount ?? '',
  availableDate: item && 'available_date' in item ? item.available_date : '',
  code: item && 'code' in item ? item.code : '',
  displayName: item?.display_name ?? '',
  isBorrowed: item && 'is_borrowed' in item ? item.is_borrowed : false,
  isEstimate: item && 'is_estimate' in item ? item.is_estimate : true,
  notes: item && 'notes' in item ? (item.notes ?? '') : '',
  sourceType: item && 'source_type' in item ? item.source_type : '',
});

function ChildDialog({
  item,
  kind,
  onClose,
  planId,
}: {
  item?: Funding | Cost;
  kind: 'cost' | 'funding';
  onClose: () => void;
  planId: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [draft, setDraft] = useState(() => childDraft(item));
  const [validation, setValidation] = useState('');
  const field =
    (key: keyof ChildDraft) => (event: React.ChangeEvent<HTMLInputElement>) =>
      setDraft((current) => ({ ...current, [key]: event.target.value }));
  const mutation = useMutation({
    mutationFn: () => {
      const segment = kind === 'funding' ? 'funding-sources' : 'costs';
      const body =
        kind === 'funding'
          ? {
              amount: draft.amount,
              available_date: draft.availableDate,
              display_name: draft.displayName.trim(),
              is_borrowed: draft.isBorrowed,
              notes: draft.notes.trim() || null,
              source_type: draft.sourceType.trim(),
            }
          : {
              amount: draft.amount,
              code: draft.code.trim().toUpperCase(),
              display_name: draft.displayName.trim(),
              is_estimate: draft.isEstimate,
            };
      return apiRequest(
        `/api/v1/purchase-plans/${planId}/${segment}${item ? `/${item.id}` : ''}`,
        {
          body: JSON.stringify(
            item ? { ...body, expected_revision: item.revision } : body,
          ),
          csrfToken: auth.csrfToken(),
          method: item ? 'PATCH' : 'POST',
        },
      );
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({
          queryKey: ['purchase-plan', planId],
        });
        notification.notify(
          'This record changed elsewhere. Review the refreshed details before trying again.',
          'warning',
        );
        onClose();
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['purchase-plan', planId],
      });
      notification.notify(
        `${kind === 'funding' ? 'Funding source' : 'Purchase cost'} saved.`,
        'success',
      );
      onClose();
    },
  });
  const submit = () => {
    if (!draft.displayName.trim() || !moneyPattern.test(draft.amount))
      return setValidation(
        'Enter a name and a non-negative amount with no more than two decimal places.',
      );
    if (
      kind === 'funding' &&
      (!draft.sourceType.trim() || !draft.availableDate)
    )
      return setValidation('Source type and available date are required.');
    if (kind === 'cost' && !draft.code.trim())
      return setValidation('A cost code is required.');
    mutation.mutate();
  };
  return (
    <Dialog fullWidth onClose={mutation.isPending ? undefined : onClose} open>
      <DialogTitle>
        {item ? 'Correct' : 'Add'}{' '}
        {kind === 'funding' ? 'funding source' : 'purchase cost'}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField
            label="Name"
            onChange={field('displayName')}
            value={draft.displayName}
          />
          {kind === 'funding' ? (
            <>
              <TextField
                label="Source type"
                onChange={field('sourceType')}
                value={draft.sourceType}
              />
              <TextField
                label="Available date"
                onChange={field('availableDate')}
                slotProps={{ inputLabel: { shrink: true } }}
                type="date"
                value={draft.availableDate}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={draft.isBorrowed}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        isBorrowed: event.target.checked,
                      }))
                    }
                  />
                }
                label="Borrowed funds"
              />
              <TextField
                label="Notes (optional)"
                multiline
                onChange={field('notes')}
                value={draft.notes}
              />
            </>
          ) : (
            <>
              <TextField
                label="Cost code"
                onChange={field('code')}
                value={draft.code}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={draft.isEstimate}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        isEstimate: event.target.checked,
                      }))
                    }
                  />
                }
                label="Estimated cost"
              />
            </>
          )}
          <TextField
            label="Amount"
            onChange={field('amount')}
            value={draft.amount}
          />
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {mutation.error ? (
            <Alert severity="error">
              Save failed. {errorMessage(mutation.error)}
            </Alert>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={mutation.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={mutation.isPending}
          onClick={submit}
          variant="contained"
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface OwnerDraft {
  externalName: string;
  ownerType: OwnerType;
  percentage: string;
  personId: string;
}

const ownerDraft = (item?: Owner): OwnerDraft => ({
  externalName: item?.external_owner_name ?? '',
  ownerType: item?.owner_type ?? 'HOUSEHOLD',
  percentage: item?.ownership_percentage ?? '100',
  personId: item?.person_id ?? '',
});

function OwnershipDialog({
  detail,
  onClose,
  people,
}: {
  detail: Detail;
  onClose: () => void;
  people: Person[];
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [rows, setRows] = useState<OwnerDraft[]>(() =>
    detail.ownership.length ? detail.ownership.map(ownerDraft) : [ownerDraft()],
  );
  const [validation, setValidation] = useState('');
  const mutation = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/purchase-plans/${detail.id}/ownership`, {
        body: JSON.stringify({
          expected_revision_ids: detail.ownership.map((item) => item.id),
          ownership: rows.map((row) => ({
            external_owner_name:
              row.ownerType === 'EXTERNAL_PARTY'
                ? row.externalName.trim()
                : null,
            owner_type: row.ownerType,
            ownership_percentage: row.percentage,
            person_id: row.ownerType === 'PERSON' ? row.personId : null,
          })),
        }),
        csrfToken: auth.csrfToken(),
        method: 'PUT',
      }),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({
          queryKey: ['purchase-plan', detail.id],
        });
        notification.notify(
          'Ownership changed elsewhere. Review the refreshed owners before trying again.',
          'warning',
        );
        onClose();
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['purchase-plan', detail.id],
      });
      notification.notify('Proposed ownership replaced.', 'success');
      onClose();
    },
  });
  const update = (index: number, change: Partial<OwnerDraft>) =>
    setRows((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index ? { ...row, ...change } : row,
      ),
    );
  const submit = () => {
    if (
      rows.some(
        (row) =>
          !percentagePattern.test(row.percentage) ||
          scaledPercentage(row.percentage) === 0n,
      )
    )
      return setValidation(
        'Each ownership percentage must be greater than 0 and no more than 100.',
      );
    if (
      rows.reduce((sum, row) => sum + scaledPercentage(row.percentage), 0n) !==
      1_000_000n
    )
      return setValidation('Ownership percentages must total exactly 100%.');
    if (rows.some((row) => row.ownerType === 'PERSON' && !row.personId))
      return setValidation(
        'Choose a household person for each person allocation.',
      );
    if (
      rows.some(
        (row) => row.ownerType === 'EXTERNAL_PARTY' && !row.externalName.trim(),
      )
    )
      return setValidation('Name each external owner.');
    mutation.mutate();
  };
  return (
    <Dialog
      fullWidth
      maxWidth="md"
      onClose={mutation.isPending ? undefined : onClose}
      open
    >
      <DialogTitle>Replace proposed ownership</DialogTitle>
      <DialogContent>
        <Alert severity="warning" sx={{ mb: 2 }}>
          Saving replaces the complete proposed ownership set shown here.
        </Alert>
        <Stack spacing={2}>
          {rows.map((row, index) => (
            <Stack
              direction={{ md: 'row', xs: 'column' }}
              key={index}
              spacing={1}
            >
              <TextField
                label="Owner type"
                onChange={(event) =>
                  update(index, {
                    externalName: '',
                    ownerType: event.target.value as OwnerType,
                    personId: '',
                  })
                }
                select
                value={row.ownerType}
              >
                <MenuItem value="HOUSEHOLD">Household jointly</MenuItem>
                <MenuItem value="PERSON">A person in this household</MenuItem>
                <MenuItem value="EXTERNAL_PARTY">Someone else</MenuItem>
              </TextField>
              {row.ownerType === 'PERSON' ? (
                <TextField
                  fullWidth
                  label="Person"
                  onChange={(event) =>
                    update(index, { personId: event.target.value })
                  }
                  select
                  value={row.personId}
                >
                  {people.map((person) => (
                    <MenuItem key={person.id} value={person.id}>
                      {person.display_name}
                    </MenuItem>
                  ))}
                </TextField>
              ) : null}
              {row.ownerType === 'EXTERNAL_PARTY' ? (
                <TextField
                  fullWidth
                  label="External owner name"
                  onChange={(event) =>
                    update(index, { externalName: event.target.value })
                  }
                  value={row.externalName}
                />
              ) : null}
              <TextField
                label="Share (%)"
                onChange={(event) =>
                  update(index, { percentage: event.target.value })
                }
                value={row.percentage}
              />
              {rows.length > 1 ? (
                <Button
                  color="error"
                  onClick={() =>
                    setRows((current) =>
                      current.filter((_, rowIndex) => rowIndex !== index),
                    )
                  }
                >
                  Remove
                </Button>
              ) : null}
            </Stack>
          ))}
          <Button
            onClick={() =>
              setRows((current) => [
                ...current,
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
            Add owner
          </Button>
          {validation ? <Alert severity="error">{validation}</Alert> : null}
          {mutation.error ? (
            <Alert severity="error">
              Save failed. {errorMessage(mutation.error)}
            </Alert>
          ) : null}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={mutation.isPending} onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={mutation.isPending}
          onClick={submit}
          variant="contained"
        >
          Replace ownership
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function PurchasePlanDetailDialog({
  canEdit,
  householdId,
  onClose,
  planId,
}: {
  canEdit: boolean;
  householdId: string;
  onClose: () => void;
  planId: string;
}) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const notification = useNotification();
  const [childEditor, setChildEditor] = useState<{
    item?: Funding | Cost;
    kind: 'cost' | 'funding';
  } | null>(null);
  const [ownershipOpen, setOwnershipOpen] = useState(false);
  const [retire, setRetire] = useState<{
    id: string;
    kind: 'cost' | 'funding';
    name: string;
    revision: number;
  } | null>(null);
  const detail = useQuery({
    queryFn: () => apiRequest<Detail>(`/api/v1/purchase-plans/${planId}`),
    queryKey: ['purchase-plan', planId],
    retry: false,
  });
  const people = useQuery({
    queryFn: () =>
      apiRequest<Person[]>(`/api/v1/households/${householdId}/people`),
    queryKey: ['people', householdId],
    retry: false,
  });
  const retireMutation = useMutation({
    mutationFn: (item: NonNullable<typeof retire>) =>
      apiRequest(
        `/api/v1/purchase-plans/${planId}/${item.kind === 'funding' ? 'funding-sources' : 'costs'}/${item.id}`,
        {
          body: JSON.stringify({ expected_revision: item.revision }),
          csrfToken: auth.csrfToken(),
          method: 'DELETE',
        },
      ),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        void queryClient.invalidateQueries({
          queryKey: ['purchase-plan', planId],
        });
        notification.notify(
          'This record changed elsewhere. Review the refreshed details before removing it.',
          'warning',
        );
        setRetire(null);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['purchase-plan', planId],
      });
      setRetire(null);
    },
  });
  if (detail.isPending || people.isPending)
    return (
      <Dialog open>
        <DialogTitle>Purchase plan details</DialogTitle>
        <DialogContent>
          <Typography>Loading…</Typography>
        </DialogContent>
      </Dialog>
    );
  if (detail.error || people.error)
    return (
      <Dialog open>
        <DialogTitle>Purchase plan details</DialogTitle>
        <DialogContent>
          <Alert severity="error">
            Details could not be loaded.{' '}
            {errorMessage(detail.error ?? people.error)}
          </Alert>
          <Button
            onClick={() => {
              void detail.refetch();
              void people.refetch();
            }}
          >
            Retry
          </Button>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  const plan = detail.data;
  const ownerName = (owner: Owner) =>
    owner.owner_type === 'HOUSEHOLD'
      ? 'Household jointly'
      : owner.owner_type === 'PERSON'
        ? (people.data.find((person) => person.id === owner.person_id)
            ?.display_name ?? 'Unavailable person')
        : (owner.external_owner_name ?? owner.owner_type);
  const actions = (kind: 'cost' | 'funding', item: Funding | Cost) =>
    canEdit ? (
      <Stack direction="row">
        <Button onClick={() => setChildEditor({ item, kind })}>Correct</Button>
        <Button
          color="error"
          onClick={() =>
            setRetire({
              id: item.id,
              kind,
              name: item.display_name,
              revision: item.revision,
            })
          }
        >
          Remove
        </Button>
      </Stack>
    ) : null;
  const fundingColumns: DataColumn<Funding>[] = [
    { key: 'name', label: 'Source', render: (item) => item.display_name },
    { key: 'type', label: 'Type', render: (item) => item.source_type },
    {
      key: 'amount',
      label: `Amount (${plan.currency})`,
      render: (item) => formatCurrency(item.amount, plan.currency),
    },
    {
      key: 'date',
      label: 'Available',
      render: (item) => formatDate(item.available_date),
    },
    {
      key: 'borrowed',
      label: 'Borrowed',
      render: (item) => (item.is_borrowed ? 'Yes' : 'No'),
    },
    ...(canEdit
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (item: Funding) => actions('funding', item),
          },
        ]
      : []),
  ];
  const costColumns: DataColumn<Cost>[] = [
    { key: 'name', label: 'Cost', render: (item) => item.display_name },
    { key: 'code', label: 'Code', render: (item) => item.code },
    {
      key: 'amount',
      label: `Amount (${plan.currency})`,
      render: (item) => formatCurrency(item.amount, plan.currency),
    },
    {
      key: 'estimate',
      label: 'Estimate',
      render: (item) => (item.is_estimate ? 'Yes' : 'No'),
    },
    ...(canEdit
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (item: Cost) => actions('cost', item),
          },
        ]
      : []),
  ];
  return (
    <Dialog fullWidth maxWidth="lg" onClose={onClose} open>
      <DialogTitle>{plan.display_name}</DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ pt: 1 }}>
          <Stack direction={{ md: 'row', xs: 'column' }} spacing={4}>
            <Typography>
              <strong>Target:</strong>{' '}
              {formatCurrency(plan.target_price_min, plan.currency)} –{' '}
              {formatCurrency(plan.target_price_max, plan.currency)}
            </Typography>
            <Typography>
              <strong>Date:</strong> {formatDate(plan.target_date)}
            </Typography>
            <Typography>
              <strong>Use:</strong> {plan.intended_use}
            </Typography>
          </Stack>
          <Stack spacing={1}>
            <Stack
              direction="row"
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Typography component="h2" variant="h6">
                Funding sources
              </Typography>
              {canEdit ? (
                <Button onClick={() => setChildEditor({ kind: 'funding' })}>
                  Add funding source
                </Button>
              ) : null}
            </Stack>
            {plan.funding_sources.length ? (
              <DataTable
                caption="Plan funding sources"
                columns={fundingColumns}
                getRowKey={(item) => item.id}
                rows={plan.funding_sources}
              />
            ) : (
              <Alert severity="info">No funding sources recorded.</Alert>
            )}
          </Stack>
          <Stack spacing={1}>
            <Stack
              direction="row"
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Typography component="h2" variant="h6">
                Purchase costs
              </Typography>
              {canEdit ? (
                <Button onClick={() => setChildEditor({ kind: 'cost' })}>
                  Add purchase cost
                </Button>
              ) : null}
            </Stack>
            {plan.costs.length ? (
              <DataTable
                caption="Plan purchase costs"
                columns={costColumns}
                getRowKey={(item) => item.id}
                rows={plan.costs}
              />
            ) : (
              <Alert severity="info">No user-entered costs recorded.</Alert>
            )}
          </Stack>
          <Stack spacing={1}>
            <Stack
              direction="row"
              sx={{ alignItems: 'center', justifyContent: 'space-between' }}
            >
              <Typography component="h2" variant="h6">
                Proposed ownership
              </Typography>
              {canEdit ? (
                <Button onClick={() => setOwnershipOpen(true)}>
                  Replace ownership
                </Button>
              ) : null}
            </Stack>
            {plan.ownership.length ? (
              <DataTable
                caption="Proposed ownership"
                columns={[
                  { key: 'owner', label: 'Owner', render: ownerName },
                  {
                    key: 'share',
                    label: 'Share',
                    render: (item) => `${item.ownership_percentage}%`,
                  },
                ]}
                getRowKey={(item) => item.id}
                rows={plan.ownership}
              />
            ) : (
              <Alert severity="info">No proposed ownership recorded.</Alert>
            )}
          </Stack>
          <PurchaseFeasibilityPanel
            key={JSON.stringify({
              costs: plan.costs.map(({ id, revision }) => [id, revision]),
              funding: plan.funding_sources.map(({ id, revision }) => [
                id,
                revision,
              ]),
              plan: {
                desiredBuffer: plan.desired_buffer,
                maxLvr: plan.max_lvr,
                minimumSurplus: plan.minimum_monthly_surplus,
                providerCode: plan.provider_code,
                providerSettings: plan.provider_settings,
                targetDate: plan.target_date,
              },
            })}
            plan={plan}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
      {childEditor ? (
        <ChildDialog
          item={childEditor.item}
          kind={childEditor.kind}
          onClose={() => setChildEditor(null)}
          planId={planId}
        />
      ) : null}
      {ownershipOpen ? (
        <OwnershipDialog
          detail={plan}
          onClose={() => setOwnershipOpen(false)}
          people={people.data}
        />
      ) : null}
      {retire ? (
        <Dialog open>
          <DialogTitle>Remove {retire.name}?</DialogTitle>
          <DialogContent>
            <Alert severity="warning">
              This removes the record from the active purchase plan and its
              financial calculations. The audited history is retained.
            </Alert>
            {retireMutation.error ? (
              <Alert severity="error" sx={{ mt: 2 }}>
                Removal failed. {errorMessage(retireMutation.error)}
              </Alert>
            ) : null}
          </DialogContent>
          <DialogActions>
            <Button
              disabled={retireMutation.isPending}
              onClick={() => setRetire(null)}
            >
              Cancel
            </Button>
            <Button
              color="error"
              disabled={retireMutation.isPending}
              onClick={() => retireMutation.mutate(retire)}
            >
              Remove
            </Button>
          </DialogActions>
        </Dialog>
      ) : null}
    </Dialog>
  );
}
