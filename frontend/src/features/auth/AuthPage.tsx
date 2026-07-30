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
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError, apiRequest } from '../../api/client';
import type { components } from '../../api/schema';
import { useAuth } from './AuthContext';

const schema = z.object({
  bootstrapToken: z.string(),
  displayName: z.string().max(200),
  password: z.string().min(6, 'Password must contain at least 6 characters'),
  username: z.string().min(1, 'Enter your username').max(320),
});
type FormValues = z.infer<typeof schema>;
type BootstrapStatus = components['schemas']['BootstrapStatusResponse'];

export function AuthPage() {
  const auth = useAuth();
  const [bootstrapRequired, setBootstrapRequired] = useState<boolean | null>(
    null,
  );
  const [error, setError] = useState<string>();
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    resetField,
  } = useForm<FormValues>({
    defaultValues: {
      bootstrapToken: '',
      displayName: '',
      password: '',
      username: '',
    },
    resolver: zodResolver(schema),
  });

  useEffect(() => {
    void apiRequest<BootstrapStatus>('/api/v1/auth/status')
      .then((response) => {
        setBootstrapRequired(response.bootstrap_required);
      })
      .catch((caught: unknown) => {
        setError(
          caught instanceof Error
            ? caught.message
            : 'Unable to check authentication status',
        );
      });
  }, []);

  const submit = handleSubmit(async (values) => {
    setError(undefined);
    try {
      if (bootstrapRequired) {
        if (!values.bootstrapToken) {
          setError('Enter the bootstrap token configured by the operator.');
          return;
        }
        await auth.bootstrap(values);
      } else {
        await auth.login(values.username, values.password);
      }
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : 'Authentication could not be completed';
      setError(message);
      resetField('password');
      if (bootstrapRequired) resetField('bootstrapToken');
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
        p: 4,
      }}
    >
      <Paper sx={{ maxWidth: 480, p: 4, width: '100%' }}>
        <Stack
          component="form"
          noValidate
          onSubmit={(event) => {
            void submit(event);
          }}
          spacing={2.5}
        >
          <div>
            <Typography component="h1" variant="h4">
              {bootstrapRequired ? 'Create the first administrator' : 'Sign in'}
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              {bootstrapRequired
                ? 'Set up the local account that will manage this installation.'
                : 'Continue planning your household finances.'}
            </Typography>
          </div>
          {auth.expired ? (
            <Alert severity="warning">
              Your session expired. Sign in again to continue.
            </Alert>
          ) : null}
          {error ? <Alert severity="error">{error}</Alert> : null}
          <TextField
            autoComplete="username"
            error={Boolean(errors.username)}
            helperText={errors.username?.message}
            label="Username"
            {...register('username')}
          />
          {bootstrapRequired ? (
            <>
              <TextField
                autoComplete="name"
                label="Display name (optional)"
                {...register('displayName')}
              />
              <TextField
                autoComplete="off"
                label="Bootstrap token"
                type="password"
                {...register('bootstrapToken')}
              />
            </>
          ) : null}
          <TextField
            autoComplete={
              bootstrapRequired ? 'new-password' : 'current-password'
            }
            error={Boolean(errors.password)}
            helperText={errors.password?.message}
            label="Password"
            type="password"
            {...register('password')}
          />
          <Button
            disabled={isSubmitting || bootstrapRequired === null}
            size="large"
            type="submit"
            variant="contained"
          >
            {bootstrapRequired ? 'Create administrator' : 'Sign in'}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
