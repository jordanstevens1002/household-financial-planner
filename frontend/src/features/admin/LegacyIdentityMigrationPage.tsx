import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { EmptyState } from '../../shared/EmptyState';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';

type AdminUser = components['schemas']['AdminUserResponse'];
type Identity = components['schemas']['LegacyIdentityResponse'];
type IdentityList = components['schemas']['LegacyIdentityListResponse'];
type MapRequest = components['schemas']['LegacyIdentityMapRequest'];
type MapResult = components['schemas']['LegacyIdentityMappedResponse'];

type TargetMode = 'existing' | 'new';

interface MappingDraft {
  displayName: string;
  email: string;
  existingAccountId: string;
  mode: TargetMode;
  username: string;
}

const emptyDraft: MappingDraft = {
  displayName: '',
  email: '',
  existingAccountId: '',
  mode: 'existing',
  username: '',
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : 'The request could not be completed';
}

function statusLabel(identity: Identity): string {
  if (identity.status === 'READY') return 'Ready';
  if (identity.status === 'ACTIVATION_PENDING') return 'Activation pending';
  return 'Not mapped';
}

export function LegacyIdentityMigrationPage() {
  const auth = useAuth();
  const { notify } = useNotification();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Identity | null>(null);
  const [draft, setDraft] = useState<MappingDraft>(emptyDraft);
  const [confirmMapping, setConfirmMapping] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(
    null,
  );
  const [acceptLoginLoss, setAcceptLoginLoss] = useState(false);
  const [completionOpen, setCompletionOpen] = useState(false);
  const [revokeIdentity, setRevokeIdentity] = useState<Identity | null>(null);

  const identities = useQuery({
    enabled: auth.account?.global_role === 'ADMIN',
    queryFn: () => apiRequest<IdentityList>('/api/v1/admin/legacy-identities'),
    queryKey: ['legacy-identities'],
  });
  const users = useQuery({
    enabled: auth.account?.global_role === 'ADMIN',
    queryFn: () => apiRequest<AdminUser[]>('/api/v1/admin/users'),
    queryKey: ['admin-users'],
  });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['legacy-identities'] });
  };
  const mapIdentity = useMutation({
    mutationFn: ({
      identity,
      payload,
    }: {
      identity: Identity;
      payload: MapRequest;
    }) =>
      apiRequest<MapResult>(
        `/api/v1/admin/legacy-identities/${identity.id}/mapping`,
        {
          body: JSON.stringify(payload),
          csrfToken: auth.csrfToken(),
          method: 'POST',
        },
      ),
    onSuccess: async (result) => {
      setConfirmMapping(false);
      setSelected(null);
      setDraft(emptyDraft);
      if (result.temporary_password) {
        setTemporaryPassword(result.temporary_password);
      }
      notify('Legacy login mapped', 'success');
      await refresh();
    },
    onError: () => setConfirmMapping(false),
  });
  const reconcile = useMutation({
    mutationFn: () =>
      apiRequest<IdentityList>('/api/v1/admin/legacy-identities/reconcile', {
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: async () => {
      notify('Household memberships reconciled', 'success');
      await refresh();
    },
  });
  const revoke = useMutation({
    mutationFn: (identity: Identity) =>
      apiRequest<void>(
        `/api/v1/admin/legacy-identities/${identity.id}/mapping`,
        { csrfToken: auth.csrfToken(), method: 'DELETE' },
      ),
    onSuccess: async () => {
      setRevokeIdentity(null);
      notify('Mapping revoked; its audit history was retained', 'success');
      await refresh();
    },
  });

  if (auth.account?.global_role !== 'ADMIN') {
    return (
      <Alert severity="error">
        A global administrator account is required to migrate legacy logins.
      </Alert>
    );
  }

  const data = identities.data;
  const mappedCount = data ? data.identities.length - data.unresolved_count : 0;
  const progress = data?.identities.length
    ? (mappedCount / data.identities.length) * 100
    : 0;
  const availableUsers =
    users.data?.filter(
      (user) =>
        user.is_active &&
        !data?.identities.some(
          (identity) => identity.mapping?.application_user_id === user.id,
        ),
    ) ?? [];
  const draftValid =
    draft.mode === 'existing'
      ? draft.existingAccountId !== ''
      : draft.username.trim() !== '';
  const request: MapRequest =
    draft.mode === 'existing'
      ? { application_user_id: draft.existingAccountId }
      : {
          new_account: {
            display_name: draft.displayName || null,
            email: draft.email || null,
            username: draft.username,
          },
        };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          Legacy login migration
        </Typography>
        <Typography color="text.secondary">
          Connect each former OIDC login to a local account before OIDC is
          retired. Financial details are not shown here.
        </Typography>
      </Box>

      {identities.isLoading || users.isLoading ? (
        <CircularProgress aria-label="Loading legacy identities" />
      ) : null}
      {identities.error || users.error ? (
        <Alert severity="error">
          {errorMessage(identities.error ?? users.error)}
        </Alert>
      ) : null}

      {data ? (
        <Paper sx={{ p: 2 }} variant="outlined">
          <Stack spacing={1}>
            <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
              <Typography sx={{ fontWeight: 700 }}>
                Migration progress
              </Typography>
              <Typography>
                {mappedCount} of {data.identities.length} ready
              </Typography>
            </Stack>
            <LinearProgress
              aria-label="Migration progress"
              value={progress}
              variant="determinate"
            />
            <Typography color="text.secondary" variant="body2">
              {data.unresolved_count} unresolved, including{' '}
              {data.activation_pending_count} awaiting password setup
            </Typography>
          </Stack>
        </Paper>
      ) : null}

      {data?.identities.length === 0 ? (
        <EmptyState
          description="No OIDC identities have been captured for migration."
          title="No legacy logins"
        />
      ) : null}

      {data?.identities.map((identity) => (
        <Paper key={identity.id} sx={{ p: 2 }} variant="outlined">
          <Stack spacing={1.5}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <Typography component="h2" sx={{ fontWeight: 700 }} variant="h6">
                {identity.display_name ||
                  identity.email ||
                  'Unnamed legacy login'}
              </Typography>
              <Chip
                color={
                  identity.status === 'READY'
                    ? 'success'
                    : identity.status === 'ACTIVATION_PENDING'
                      ? 'warning'
                      : 'default'
                }
                label={statusLabel(identity)}
                size="small"
              />
            </Stack>
            {identity.email ? (
              <Typography color="text.secondary">{identity.email}</Typography>
            ) : null}
            <Typography color="text.secondary" variant="body2">
              Legacy subject: {identity.oidc_subject}
            </Typography>
            <Box>
              <Typography sx={{ fontWeight: 600 }}>Household access</Typography>
              {identity.memberships.length ? (
                identity.memberships.map((membership) => (
                  <Chip
                    key={membership.household_id}
                    label={`${membership.household_name} · ${membership.role}`}
                    size="small"
                    sx={{ mr: 1, mt: 1 }}
                    variant="outlined"
                  />
                ))
              ) : (
                <Typography color="text.secondary" variant="body2">
                  No household memberships
                </Typography>
              )}
            </Box>
            {identity.mapping ? (
              <Alert
                severity={identity.status === 'READY' ? 'success' : 'warning'}
              >
                Mapped to{' '}
                {identity.mapping.display_name || identity.mapping.username}.
                {identity.status === 'ACTIVATION_PENDING'
                  ? ' This account must complete password setup before cutover.'
                  : ''}
              </Alert>
            ) : null}
            <Stack direction="row" spacing={1}>
              {identity.mapping ? (
                <Button
                  color="error"
                  onClick={() => setRevokeIdentity(identity)}
                  size="small"
                >
                  Correct mapping
                </Button>
              ) : (
                <Button
                  onClick={() => {
                    setSelected(identity);
                    setDraft({
                      ...emptyDraft,
                      displayName: identity.display_name ?? '',
                      email: identity.email ?? '',
                    });
                  }}
                  size="small"
                  variant="contained"
                >
                  Map login
                </Button>
              )}
            </Stack>
          </Stack>
        </Paper>
      ))}

      {data && data.identities.length > 0 ? (
        <Paper sx={{ p: 2 }} variant="outlined">
          <Stack spacing={2}>
            <Typography component="h2" variant="h6">
              Complete migration review
            </Typography>
            {!data.cutover_ready ? (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={acceptLoginLoss}
                    onChange={(event) =>
                      setAcceptLoginLoss(event.target.checked)
                    }
                  />
                }
                label={`Accept that ${data.unresolved_count} unresolved login(s) will lose access`}
              />
            ) : (
              <Alert severity="success">
                Every legacy login has a usable local account.
              </Alert>
            )}
            <Stack direction="row" spacing={1}>
              <Button
                disabled={reconcile.isPending}
                onClick={() => reconcile.mutate()}
                variant="outlined"
              >
                Reconcile memberships
              </Button>
              <Button
                disabled={!data.cutover_ready && !acceptLoginLoss}
                onClick={() => setCompletionOpen(true)}
                variant="contained"
              >
                Complete review
              </Button>
            </Stack>
            {reconcile.error ? (
              <Alert severity="error">{errorMessage(reconcile.error)}</Alert>
            ) : null}
          </Stack>
        </Paper>
      ) : null}

      <Dialog onClose={() => setSelected(null)} open={selected !== null}>
        <DialogTitle>
          Map {selected?.display_name || selected?.email || 'legacy login'}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1, minWidth: 460 }}>
            <TextField
              label="Account target"
              onChange={(event) =>
                setDraft({ ...draft, mode: event.target.value as TargetMode })
              }
              select
              value={draft.mode}
            >
              <MenuItem value="existing">Existing local account</MenuItem>
              <MenuItem value="new">Create a new local account</MenuItem>
            </TextField>
            {draft.mode === 'existing' ? (
              <TextField
                label="Local account"
                onChange={(event) =>
                  setDraft({ ...draft, existingAccountId: event.target.value })
                }
                select
                value={draft.existingAccountId}
              >
                {availableUsers.map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {user.display_name || user.username} ({user.username})
                  </MenuItem>
                ))}
              </TextField>
            ) : (
              <>
                <TextField
                  label="Username"
                  onChange={(event) =>
                    setDraft({ ...draft, username: event.target.value })
                  }
                  value={draft.username}
                />
                <TextField
                  label="Display name"
                  onChange={(event) =>
                    setDraft({ ...draft, displayName: event.target.value })
                  }
                  value={draft.displayName}
                />
                <TextField
                  label="Email (optional)"
                  onChange={(event) =>
                    setDraft({ ...draft, email: event.target.value })
                  }
                  value={draft.email}
                />
              </>
            )}
            {mapIdentity.error ? (
              <Alert severity="error">{errorMessage(mapIdentity.error)}</Alert>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelected(null)}>Cancel</Button>
          <Button
            disabled={!draftValid}
            onClick={() => setConfirmMapping(true)}
            variant="contained"
          >
            Review mapping
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        confirmLabel="Confirm mapping"
        description={`This will transfer ${selected?.memberships.length ?? 0} household membership(s) to the selected local account. Confirm that this is the correct person.`}
        onCancel={() => setConfirmMapping(false)}
        onConfirm={() => {
          if (selected)
            mapIdentity.mutate({ identity: selected, payload: request });
        }}
        open={confirmMapping}
        pending={mapIdentity.isPending}
        title="Confirm identity mapping"
      />
      <ConfirmDialog
        confirmLabel="Revoke mapping"
        description="This removes access inherited through this mapping and retains an audit record. You can then select the correct account."
        onCancel={() => setRevokeIdentity(null)}
        onConfirm={() => {
          if (revokeIdentity) revoke.mutate(revokeIdentity);
        }}
        open={revokeIdentity !== null}
        pending={revoke.isPending}
        title="Correct identity mapping"
      />

      <Dialog open={temporaryPassword !== null}>
        <DialogTitle>Temporary password</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Give this password directly to the user. It is shown once and they
            must change it before the mapping is ready.
          </Alert>
          <TextField
            fullWidth
            label="One-time temporary password"
            slotProps={{ input: { readOnly: true } }}
            value={temporaryPassword ?? ''}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setTemporaryPassword(null)}
            variant="contained"
          >
            I have saved it
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={completionOpen}>
        <DialogTitle>Migration review complete</DialogTitle>
        <DialogContent>
          <Alert severity={data?.cutover_ready ? 'success' : 'warning'}>
            {data?.cutover_ready
              ? 'Every captured legacy login is mapped to a usable local account.'
              : `You accepted that ${data?.unresolved_count ?? 0} unresolved login(s) may lose access.`}
          </Alert>
          <Typography sx={{ mt: 2 }}>
            Run membership reconciliation again immediately before the later
            authentication cutover.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCompletionOpen(false)} variant="contained">
            Close report
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
