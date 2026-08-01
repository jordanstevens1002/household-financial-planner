import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
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
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';
import { type Household, useHousehold } from './HouseholdContext';

type Country = components['schemas']['CountryRead'];
type Currency = components['schemas']['CurrencyRead'];
type Membership = components['schemas']['MembershipRead'];
type HouseholdRole = components['schemas']['HouseholdRole'];

const householdSchema = z.object({
  currency: z.string().min(1, 'Choose a currency'),
  displayName: z.string().trim().min(1, 'Enter a household name').max(200),
  jurisdiction: z.string().min(1, 'Choose a country'),
});
const membershipSchema = z.object({
  role: z.enum(['OWNER', 'ADMIN', 'EDITOR', 'VIEWER']),
  username: z.string().trim().min(1, 'Enter a username'),
});
type HouseholdFields = z.infer<typeof householdSchema>;
type MembershipFields = z.infer<typeof membershipSchema>;

const roleRank: Record<HouseholdRole, number> = {
  OWNER: 4,
  ADMIN: 3,
  EDITOR: 2,
  VIEWER: 1,
};

function message(error: unknown) {
  return error instanceof ApiError ? error.message : 'The request failed';
}

export function HouseholdsPage() {
  const auth = useAuth();
  const household = useHousehold();
  const queryClient = useQueryClient();
  const { notify } = useNotification();
  const [createOpen, setCreateOpen] = useState(false);
  const [memberOpen, setMemberOpen] = useState(false);
  const [pendingRemoval, setPendingRemoval] = useState<Membership | null>(null);
  const householdForm = useForm<HouseholdFields>({
    defaultValues: { currency: '', displayName: '', jurisdiction: '' },
    resolver: zodResolver(householdSchema),
  });
  const memberForm = useForm<MembershipFields>({
    defaultValues: { role: 'VIEWER', username: '' },
    resolver: zodResolver(membershipSchema),
  });
  const countries = useQuery({
    queryFn: () => apiRequest<Country[]>('/api/v1/reference/countries'),
    queryKey: ['reference', 'countries'],
  });
  const currencies = useQuery({
    queryFn: () => apiRequest<Currency[]>('/api/v1/reference/currencies'),
    queryKey: ['reference', 'currencies'],
  });
  const members = useQuery({
    enabled: household.selected !== null,
    queryFn: () =>
      apiRequest<Membership[]>(
        `/api/v1/households/${household.selected!.id}/memberships`,
      ),
    queryKey: ['household-memberships', household.selected?.id],
    retry: false,
  });
  const actor = members.data?.find(
    (item) => item.application_user_id === auth.account?.id,
  );
  const canManage = actor?.role === 'OWNER' || actor?.role === 'ADMIN';

  const refreshMembers = () =>
    queryClient.invalidateQueries({
      queryKey: ['household-memberships', household.selected?.id],
    });
  const createHousehold = useMutation({
    mutationFn: (fields: HouseholdFields) =>
      apiRequest<Household>('/api/v1/households', {
        body: JSON.stringify({
          currency: fields.currency,
          display_name: fields.displayName,
          jurisdiction: fields.jurisdiction,
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: (created) => {
      household.add(created);
      household.select(created);
      householdForm.reset();
      setCreateOpen(false);
      notify('Household created', 'success');
    },
  });
  const addMember = useMutation({
    mutationFn: (fields: MembershipFields) =>
      apiRequest<Membership>(
        `/api/v1/households/${household.selected!.id}/memberships`,
        {
          body: JSON.stringify(fields),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      ),
    onSuccess: async () => {
      setMemberOpen(false);
      memberForm.reset();
      notify('Household member added', 'success');
      await refreshMembers();
    },
  });
  const updateMember = useMutation({
    mutationFn: ({ id, role }: { id: string; role: HouseholdRole }) =>
      apiRequest<Membership>(
        `/api/v1/households/${household.selected!.id}/memberships/${id}`,
        {
          body: JSON.stringify({ role }),
          csrfToken: auth.csrfToken(),
          method: 'PATCH',
        },
      ),
    onSuccess: async () => {
      notify('Household role updated', 'success');
      await refreshMembers();
    },
  });
  const removeMember = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(
        `/api/v1/households/${household.selected!.id}/memberships/${id}`,
        { csrfToken: auth.csrfToken(), method: 'DELETE' },
      ),
    onSuccess: async () => {
      setPendingRemoval(null);
      notify('Household member removed', 'success');
      await refreshMembers();
    },
  });
  const actionError =
    createHousehold.error ??
    addMember.error ??
    updateMember.error ??
    removeMember.error;

  const columns: DataColumn<Household>[] = [
    { key: 'name', label: 'Household', render: (row) => row.display_name },
    { key: 'currency', label: 'Currency', render: (row) => row.currency },
    {
      key: 'country',
      label: 'Country',
      render: (row) => row.jurisdiction ?? 'Not recorded',
    },
    {
      key: 'action',
      label: 'Selection',
      render: (row) => (
        <Button
          onClick={() => household.select(row)}
          variant={household.selected?.id === row.id ? 'contained' : 'outlined'}
        >
          {household.selected?.id === row.id ? 'Selected' : 'Use household'}
        </Button>
      ),
    },
  ];
  const memberColumns: DataColumn<Membership>[] = [
    {
      key: 'account',
      label: 'Account',
      render: (row) => row.display_name || row.username || 'Legacy account',
    },
    {
      key: 'role',
      label: 'Household role',
      render: (row) =>
        canManage &&
        (actor?.role === 'OWNER' || roleRank[row.role] < roleRank.OWNER) ? (
          <TextField
            aria-label={`Role for ${row.username ?? row.display_name}`}
            disabled={updateMember.isPending}
            onChange={(event) =>
              updateMember.mutate({
                id: row.id,
                role: event.target.value as HouseholdRole,
              })
            }
            select
            size="small"
            value={row.role}
          >
            {(['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] as HouseholdRole[])
              .filter((role) => actor?.role === 'OWNER' || role !== 'OWNER')
              .map((role) => (
                <MenuItem key={role} value={role}>
                  {role}
                </MenuItem>
              ))}
          </TextField>
        ) : (
          <Chip label={row.role} />
        ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => (row.is_active ? 'Active' : 'Disabled'),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) =>
        canManage &&
        row.application_user_id !== auth.account?.id &&
        (actor?.role === 'OWNER' || row.role !== 'OWNER') ? (
          <Button color="error" onClick={() => setPendingRemoval(row)}>
            Remove
          </Button>
        ) : null,
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Households
        </Typography>
        <Typography color="text.secondary">
          Choose the household whose finances you want to explore.
        </Typography>
      </Box>
      {actionError ? (
        <Alert severity="error">{message(actionError)}</Alert>
      ) : null}
      <Box>
        <Button onClick={() => setCreateOpen(true)} variant="contained">
          Create household
        </Button>
      </Box>
      {household.loading ? (
        <CircularProgress aria-label="Loading households" />
      ) : household.households.length ? (
        <DataTable
          caption="Your households"
          columns={columns}
          getRowKey={(row) => row.id}
          rows={household.households}
        />
      ) : (
        <EmptyState
          actionLabel="Create your first household"
          description="Create a household to begin organising shared finances."
          onAction={() => setCreateOpen(true)}
          title="No households yet"
        />
      )}

      {household.selected ? (
        <Stack spacing={2}>
          <Box>
            <Typography component="h2" variant="h5">
              {household.selected.display_name} members
            </Typography>
            <Typography color="text.secondary">
              Global account roles and household access are separate.
            </Typography>
          </Box>
          {members.isPending ? (
            <CircularProgress aria-label="Loading members" />
          ) : members.error instanceof ApiError &&
            members.error.status === 403 ? (
            <Alert severity="info">
              Only household owners and administrators can manage memberships.
            </Alert>
          ) : members.data ? (
            <>
              {canManage ? (
                <Box>
                  <Button
                    onClick={() => setMemberOpen(true)}
                    variant="outlined"
                  >
                    Add member
                  </Button>
                </Box>
              ) : null}
              <DataTable
                caption={`${household.selected.display_name} memberships`}
                columns={memberColumns}
                getRowKey={(row) => row.id}
                rows={members.data}
              />
            </>
          ) : (
            <Alert severity="error">
              Could not load household memberships.
            </Alert>
          )}
        </Stack>
      ) : (
        <Alert severity="info">Select a household to manage its members.</Alert>
      )}

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth>
        <DialogTitle>Create household</DialogTitle>
        <Box
          component="form"
          onSubmit={(event) => {
            void householdForm.handleSubmit((fields) =>
              createHousehold.mutate(fields),
            )(event);
          }}
        >
          <DialogContent>
            <Stack spacing={2}>
              <TextField
                label="Household name"
                {...householdForm.register('displayName')}
                error={Boolean(householdForm.formState.errors.displayName)}
                helperText={householdForm.formState.errors.displayName?.message}
              />
              <Controller
                control={householdForm.control}
                name="jurisdiction"
                render={({ field, fieldState }) => (
                  <Autocomplete
                    options={countries.data ?? []}
                    getOptionLabel={(option) =>
                      `${option.flag} ${option.display_name}`
                    }
                    value={
                      (countries.data ?? []).find(
                        (item) => item.code === field.value,
                      ) ?? null
                    }
                    onChange={(_, option) => field.onChange(option?.code ?? '')}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Country"
                        error={Boolean(fieldState.error)}
                        helperText={fieldState.error?.message}
                      />
                    )}
                  />
                )}
              />
              <Controller
                control={householdForm.control}
                name="currency"
                render={({ field, fieldState }) => (
                  <Autocomplete
                    options={currencies.data ?? []}
                    getOptionLabel={(option) =>
                      `${option.code} — ${option.display_name}`
                    }
                    value={
                      (currencies.data ?? []).find(
                        (item) => item.code === field.value,
                      ) ?? null
                    }
                    onChange={(_, option) => field.onChange(option?.code ?? '')}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Currency"
                        error={Boolean(fieldState.error)}
                        helperText={fieldState.error?.message}
                      />
                    )}
                  />
                )}
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={createHousehold.isPending}
              type="submit"
              variant="contained"
            >
              Create
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
      <Dialog open={memberOpen} onClose={() => setMemberOpen(false)} fullWidth>
        <DialogTitle>Add household member</DialogTitle>
        <Box
          component="form"
          onSubmit={(event) => {
            void memberForm.handleSubmit((fields) => addMember.mutate(fields))(
              event,
            );
          }}
        >
          <DialogContent>
            <Stack spacing={2}>
              <TextField
                label="Local account username"
                {...memberForm.register('username')}
                error={Boolean(memberForm.formState.errors.username)}
                helperText={
                  memberForm.formState.errors.username?.message ??
                  'The account must already exist.'
                }
              />
              <TextField
                defaultValue="VIEWER"
                label="Household role"
                select
                {...memberForm.register('role')}
              >
                {(['OWNER', 'ADMIN', 'EDITOR', 'VIEWER'] as HouseholdRole[])
                  .filter((role) => actor?.role === 'OWNER' || role !== 'OWNER')
                  .map((role) => (
                    <MenuItem key={role} value={role}>
                      {role}
                    </MenuItem>
                  ))}
              </TextField>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setMemberOpen(false)}>Cancel</Button>
            <Button
              disabled={addMember.isPending}
              type="submit"
              variant="contained"
            >
              Add member
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
      <ConfirmDialog
        confirmLabel="Remove member"
        description={`Remove ${pendingRemoval?.display_name || pendingRemoval?.username || 'this account'} from ${household.selected?.display_name ?? 'this household'}?`}
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() =>
          pendingRemoval && removeMember.mutate(pendingRemoval.id)
        }
        open={pendingRemoval !== null}
        pending={removeMember.isPending}
        title="Remove household member?"
      />
    </Stack>
  );
}
