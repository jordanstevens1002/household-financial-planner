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
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { useAuth } from './AuthContext';

const schema = z
  .object({
    confirmPassword: z.string(),
    currentPassword: z.string().min(1, 'Enter your temporary password'),
    newPassword: z
      .string()
      .min(6, 'New password must contain at least 6 characters'),
  })
  .refine((value) => value.newPassword === value.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });
type FormValues = z.infer<typeof schema>;

export function PasswordChangePage() {
  const auth = useAuth();
  const [error, setError] = useState<string>();
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    resetField,
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const submit = handleSubmit(async (values) => {
    setError(undefined);
    try {
      await auth.changePassword(values.currentPassword, values.newPassword);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Password change failed',
      );
      resetField('currentPassword');
      resetField('newPassword');
      resetField('confirmPassword');
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
              Choose a new password
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Your temporary password must be replaced before continuing.
            </Typography>
          </div>
          {error ? <Alert severity="error">{error}</Alert> : null}
          <TextField
            autoComplete="current-password"
            error={Boolean(errors.currentPassword)}
            helperText={errors.currentPassword?.message}
            label="Temporary password"
            type="password"
            {...register('currentPassword')}
          />
          <TextField
            autoComplete="new-password"
            error={Boolean(errors.newPassword)}
            helperText={errors.newPassword?.message}
            label="New password"
            type="password"
            {...register('newPassword')}
          />
          <TextField
            autoComplete="new-password"
            error={Boolean(errors.confirmPassword)}
            helperText={errors.confirmPassword?.message}
            label="Confirm new password"
            type="password"
            {...register('confirmPassword')}
          />
          <Button disabled={isSubmitting} type="submit" variant="contained">
            Save password
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
