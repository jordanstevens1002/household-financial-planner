import { Button, Paper, Stack, Typography } from '@mui/material';

interface EmptyStateProps {
  actionLabel?: string;
  description: string;
  onAction?: () => void;
  title: string;
}

export function EmptyState({
  actionLabel,
  description,
  onAction,
  title,
}: EmptyStateProps) {
  return (
    <Paper variant="outlined" sx={{ p: 4 }}>
      <Stack spacing={1.5} sx={{ alignItems: 'flex-start' }}>
        <Typography component="h2" variant="h6">
          {title}
        </Typography>
        <Typography color="text.secondary">{description}</Typography>
        {actionLabel && onAction ? (
          <Button onClick={onAction} variant="contained">
            {actionLabel}
          </Button>
        ) : null}
      </Stack>
    </Paper>
  );
}
