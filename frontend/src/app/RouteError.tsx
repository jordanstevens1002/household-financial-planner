import { Alert, Button, Stack, Typography } from '@mui/material';
import { useRouter } from '@tanstack/react-router';

export function RouteError({ error }: { error: Error }) {
  const router = useRouter();

  return (
    <Stack spacing={2}>
      <Typography component="h1" variant="h1">
        This page could not be loaded
      </Typography>
      <Alert severity="error">{error.message}</Alert>
      <Button
        onClick={() => {
          void router.invalidate();
        }}
        sx={{ alignSelf: 'flex-start' }}
        variant="contained"
      >
        Try again
      </Button>
    </Stack>
  );
}
