import { zodResolver } from '@hookform/resolvers/zod';
import {
  Alert,
  Box,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Link, useRouterState } from '@tanstack/react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError, apiRequest } from '../../api/client';

const schema = z
  .object({
    confirmPassword: z.string(),
    password: z.string().min(6, 'Use at least 6 characters'),
  })
  .refine((value) => value.password === value.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });
type Fields = z.infer<typeof schema>;

export function PasswordResetPage() {
  const href = useRouterState({ select: (state) => state.location.href });
  const token = new URL(href, window.location.origin).searchParams.get('token');
  const [error, setError] = useState<string>();
  const [complete, setComplete] = useState(false);
  const form = useForm<Fields>({
    defaultValues: { confirmPassword: '', password: '' },
    resolver: zodResolver(schema),
  });
  const submit = form.handleSubmit(async (fields) => {
    if (!token) {
      setError('This reset path is missing its one-time token.');
      return;
    }
    setError(undefined);
    try {
      await apiRequest<void>('/api/v1/auth/password/reset', {
        body: JSON.stringify({ new_password: fields.password, token }),
        method: 'POST',
        suppressUnauthorisedEvent: true,
      });
      setComplete(true);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Password reset failed',
      );
    }
  });

  return (
    <Box
      component="main"
      sx={{
        alignItems: 'center',
        display: 'flex',
        justifyContent: 'center',
        minHeight: '100vh',
        minWidth: 1024,
      }}
    >
      <Paper sx={{ maxWidth: 480, p: 4, width: '100%' }}>
        {complete ? (
          <Stack spacing={2}>
            <Typography component="h1" variant="h4">
              Password updated
            </Typography>
            <Alert severity="success">
              The reset path has been used and cannot be reused.
            </Alert>
            <Button component={Link} to="/" variant="contained">
              Continue to sign in
            </Button>
          </Stack>
        ) : (
          <Stack
            component="form"
            onSubmit={(event) => {
              void submit(event);
            }}
            spacing={2}
          >
            <Typography component="h1" variant="h4">
              Reset your password
            </Typography>
            <Typography color="text.secondary">
              Choose a new password using the single-use path provided by an
              administrator.
            </Typography>
            {error ? <Alert severity="error">{error}</Alert> : null}
            <TextField
              error={Boolean(form.formState.errors.password)}
              helperText={form.formState.errors.password?.message}
              label="New password"
              type="password"
              {...form.register('password')}
            />
            <TextField
              error={Boolean(form.formState.errors.confirmPassword)}
              helperText={form.formState.errors.confirmPassword?.message}
              label="Confirm new password"
              type="password"
              {...form.register('confirmPassword')}
            />
            <Button type="submit" variant="contained">
              Reset password
            </Button>
          </Stack>
        )}
      </Paper>
    </Box>
  );
}
