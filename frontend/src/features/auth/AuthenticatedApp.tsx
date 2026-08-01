import { CircularProgress, Stack, Typography } from '@mui/material';
import { useRouterState } from '@tanstack/react-router';

import { AppShell } from '../../app/AppShell';
import { useAuth } from './AuthContext';
import { AuthPage } from './AuthPage';
import { PasswordChangePage } from './PasswordChangePage';
import { PasswordResetPage } from './PasswordResetPage';
import { HouseholdProvider } from '../households/HouseholdContext';

export function AuthenticatedApp() {
  const auth = useAuth();
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  if (pathname === '/reset-password') return <PasswordResetPage />;
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
  return (
    <HouseholdProvider key={auth.account.id} sessionAccountId={auth.account.id}>
      <AppShell />
    </HouseholdProvider>
  );
}
