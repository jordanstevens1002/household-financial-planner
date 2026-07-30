import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
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
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { ConfirmDialog } from '../../shared/ConfirmDialog';
import { DataTable, type DataColumn } from '../../shared/DataTable';
import { EmptyState } from '../../shared/EmptyState';
import { useNotification } from '../../shared/notificationContext';
import { useAuth } from '../auth/AuthContext';

type AdminUser = components['schemas']['AdminUserResponse'];
type CreatedUser = components['schemas']['AdminUserCreated'];
type ResetIssued = components['schemas']['PasswordResetIssued'];
type UserUpdate = components['schemas']['AdminUserUpdate'];

const createSchema = z.object({
  displayName: z.string().max(200),
  email: z.union([z.literal(''), z.email()]),
  globalRole: z.enum(['ADMIN', 'USER']),
  username: z.string().trim().min(1, 'Enter a username').max(320),
});
type CreateFields = z.infer<typeof createSchema>;

interface PendingAction {
  kind: 'demote' | 'disable' | 'reset';
  user: AdminUser;
}

interface OneTimeResult {
  label: string;
  value: string;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : 'The request could not be completed';
}

export function AdminUsersPage() {
  const auth = useAuth();
  const { notify } = useNotification();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [oneTimeResult, setOneTimeResult] = useState<OneTimeResult | null>(
    null,
  );
  const form = useForm<CreateFields>({
    defaultValues: {
      displayName: '',
      email: '',
      globalRole: 'USER',
      username: '',
    },
    resolver: zodResolver(createSchema),
  });

  const users = useQuery({
    enabled: auth.account?.global_role === 'ADMIN',
    queryFn: () => apiRequest<AdminUser[]>('/api/v1/admin/users'),
    queryKey: ['admin-users'],
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin-users'] });
  };
  const createUser = useMutation({
    mutationFn: (fields: CreateFields) =>
      apiRequest<CreatedUser>('/api/v1/admin/users', {
        body: JSON.stringify({
          display_name: fields.displayName || null,
          email: fields.email || null,
          global_role: fields.globalRole,
          username: fields.username,
        }),
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: async (result) => {
      setCreateOpen(false);
      form.reset();
      setOneTimeResult({
        label: `Temporary password for ${result.account.username}`,
        value: result.temporary_password,
      });
      await refresh();
    },
  });
  const updateUser = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UserUpdate }) =>
      apiRequest<AdminUser>(`/api/v1/admin/users/${id}`, {
        body: JSON.stringify(payload),
        csrfToken: auth.csrfToken(),
        method: 'PATCH',
      }),
    onSuccess: async () => {
      setPending(null);
      notify('Account updated', 'success');
      await refresh();
    },
    onError: () => {
      setPending(null);
    },
  });
  const resetPassword = useMutation({
    mutationFn: (user: AdminUser) =>
      apiRequest<ResetIssued>(`/api/v1/admin/users/${user.id}/password-reset`, {
        csrfToken: auth.csrfToken(),
        method: 'POST',
      }),
    onSuccess: (result, user) => {
      setPending(null);
      setOneTimeResult({
        label: `Single-use reset path for ${user.username}`,
        value: new URL(result.reset_path, window.location.origin).toString(),
      });
    },
    onError: () => {
      setPending(null);
    },
  });

  if (auth.account?.global_role !== 'ADMIN') {
    return (
      <Stack spacing={2}>
        <Typography component="h1" variant="h4">
          User administration
        </Typography>
        <Alert severity="error">
          A global administrator account is required. Household roles do not
          grant access here.
        </Alert>
      </Stack>
    );
  }

  const performPending = () => {
    if (pending === null) return;
    if (pending.kind === 'reset') {
      resetPassword.mutate(pending.user);
      return;
    }
    updateUser.mutate({
      id: pending.user.id,
      payload:
        pending.kind === 'disable'
          ? {
              confirm_self_lockout: pending.user.id === auth.account?.id,
              is_active: false,
            }
          : {
              confirm_self_lockout: pending.user.id === auth.account?.id,
              global_role: 'USER',
            },
    });
  };
  const actionError = updateUser.error ?? resetPassword.error;
  const columns: DataColumn<AdminUser>[] = [
    {
      key: 'account',
      label: 'Account',
      render: (user) => (
        <Box>
          <Typography sx={{ fontWeight: 600 }}>
            {user.display_name || user.username}
          </Typography>
          <Typography color="text.secondary" variant="body2">
            {user.username}
          </Typography>
        </Box>
      ),
    },
    {
      key: 'global-role',
      label: 'Global account role',
      render: (user) => (
        <Chip
          color={user.global_role === 'ADMIN' ? 'primary' : 'default'}
          label={user.global_role}
        />
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (user) =>
        user.is_active
          ? user.must_change_password
            ? 'Password change required'
            : 'Active'
          : 'Disabled',
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (user) => (
        <Stack direction="row" spacing={1}>
          {user.global_role === 'USER' ? (
            <Button
              onClick={() => {
                updateUser.mutate({
                  id: user.id,
                  payload: {
                    confirm_self_lockout: false,
                    global_role: 'ADMIN',
                  },
                });
              }}
              size="small"
            >
              Make administrator
            </Button>
          ) : (
            <Button
              onClick={() => {
                setPending({ kind: 'demote', user });
              }}
              size="small"
            >
              Change to user
            </Button>
          )}
          {user.is_active ? (
            <Button
              color="error"
              onClick={() => {
                setPending({ kind: 'disable', user });
              }}
              size="small"
            >
              Disable
            </Button>
          ) : (
            <Button
              onClick={() => {
                updateUser.mutate({
                  id: user.id,
                  payload: {
                    confirm_self_lockout: false,
                    is_active: true,
                  },
                });
              }}
              size="small"
            >
              Enable
            </Button>
          )}
          <Button
            disabled={!user.is_active}
            onClick={() => {
              setPending({ kind: 'reset', user });
            }}
            size="small"
          >
            Reset password
          </Button>
        </Stack>
      ),
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography component="h1" variant="h4">
          User administration
        </Typography>
        <Typography color="text.secondary">
          Global roles manage accounts only. Household membership separately
          controls access to financial information.
        </Typography>
      </Box>
      <Alert severity="info">
        The final recovery-capable administrator cannot be disabled or changed
        to a user.
      </Alert>
      <Box>
        <Button
          onClick={() => {
            setCreateOpen(true);
          }}
          variant="contained"
        >
          Add user
        </Button>
      </Box>
      {users.isLoading ? <CircularProgress aria-label="Loading users" /> : null}
      {users.error ? (
        <Alert severity="error">{errorMessage(users.error)}</Alert>
      ) : null}
      {users.data?.length === 0 ? (
        <EmptyState
          actionLabel="Add user"
          description="Create a local account and hand its temporary password directly to the user."
          onAction={() => {
            setCreateOpen(true);
          }}
          title="No local users"
        />
      ) : null}
      {users.data && users.data.length > 0 ? (
        <DataTable
          caption="Local application users"
          columns={columns}
          getRowKey={(user) => user.id}
          rows={users.data}
        />
      ) : null}
      {actionError ? (
        <Alert severity="error">{errorMessage(actionError)}</Alert>
      ) : null}

      <Dialog onClose={() => setCreateOpen(false)} open={createOpen}>
        <Box
          component="form"
          onSubmit={(event) => {
            void form.handleSubmit((fields) => {
              createUser.mutate(fields);
            })(event);
          }}
        >
          <DialogTitle>Add local user</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ mt: 1, minWidth: 420 }}>
              <TextField
                autoFocus
                error={Boolean(form.formState.errors.username)}
                helperText={form.formState.errors.username?.message}
                label="Username"
                {...form.register('username')}
              />
              <TextField
                label="Display name"
                {...form.register('displayName')}
              />
              <TextField
                error={Boolean(form.formState.errors.email)}
                helperText={form.formState.errors.email?.message}
                label="Email (optional)"
                {...form.register('email')}
              />
              <TextField
                label="Global account role"
                select
                {...form.register('globalRole')}
              >
                <MenuItem value="USER">User</MenuItem>
                <MenuItem value="ADMIN">Administrator</MenuItem>
              </TextField>
              {createUser.error ? (
                <Alert severity="error">{errorMessage(createUser.error)}</Alert>
              ) : null}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={createUser.isPending}
              type="submit"
              variant="contained"
            >
              Create user
            </Button>
          </DialogActions>
        </Box>
      </Dialog>

      <Dialog open={oneTimeResult !== null}>
        <DialogTitle>{oneTimeResult?.label}</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This secret is shown once. Copy it before closing this message.
          </Alert>
          <TextField
            fullWidth
            label="One-time secret"
            slotProps={{ input: { readOnly: true } }}
            value={oneTimeResult?.value ?? ''}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              if (oneTimeResult) {
                void navigator.clipboard.writeText(oneTimeResult.value);
                notify('Copied to clipboard', 'success');
              }
            }}
          >
            Copy
          </Button>
          <Button onClick={() => setOneTimeResult(null)} variant="contained">
            I have saved it
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        confirmLabel={
          pending?.kind === 'reset'
            ? 'Generate reset path'
            : pending?.kind === 'disable'
              ? 'Disable account'
              : 'Change role'
        }
        description={
          pending?.user.id === auth.account?.id
            ? 'This affects your own administrator account. Continue only when another administrator has completed password setup and can sign in.'
            : pending?.kind === 'reset'
              ? 'Existing sessions and reset links for this account will stop working.'
              : 'This account may lose access to account administration.'
        }
        onCancel={() => setPending(null)}
        onConfirm={performPending}
        open={pending !== null}
        title="Confirm account change"
      />
    </Stack>
  );
}
