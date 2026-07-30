import { CircularProgress, Stack, Typography } from '@mui/material';

import { AppShell } from '../../app/AppShell';
import { useAuth } from './AuthContext';
import { AuthPage } from './AuthPage';
import { PasswordChangePage } from './PasswordChangePage';

export function AuthenticatedApp() {
  const auth = useAuth();
  if (auth.loading) {
    return (
      <Stack
        role="status"
        spacing={2}
        sx={{
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          minWidth: 1024,
        }}
      >
        <CircularProgress />
        <Typography>Checking your session…</Typography>
      </Stack>
    );
  }
  if (auth.account === null) return <AuthPage />;
  if (auth.account.must_change_password) return <PasswordChangePage />;
  return <AppShell />;
}
