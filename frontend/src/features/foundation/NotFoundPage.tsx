import { Button, Stack, Typography } from '@mui/material';
import { Link } from '@tanstack/react-router';

export function NotFoundPage() {
  return (
    <Stack spacing={2}>
      <Typography component="h1" variant="h1">
        Page not found
      </Typography>
      <Typography color="text.secondary">
        The address does not match a page in the financial planner.
      </Typography>
      <Button
        component={Link}
        sx={{ alignSelf: 'flex-start' }}
        to="/"
        variant="contained"
      >
        Return to overview
      </Button>
    </Stack>
  );
}
