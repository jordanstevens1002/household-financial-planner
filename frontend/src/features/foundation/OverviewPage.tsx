import { Alert, Button, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';

import { useNotification } from '../../shared/notificationContext';

export function OverviewPage() {
  const [showDetails, setShowDetails] = useState(false);
  const { notify } = useNotification();

  return (
    <Stack spacing={3}>
      <div>
        <Typography component="h1" variant="h1">
          Household overview
        </Typography>
        <Typography color="text.secondary">
          A clear starting point for exploring your household finances.
        </Typography>
      </div>
      <Alert severity="info">
        The React interface is being built alongside Appsmith. Each navigation
        area will become available after its tested migration slice is merged.
      </Alert>
      <Paper sx={{ p: 3 }} variant="outlined">
        <Stack spacing={2} sx={{ alignItems: 'flex-start' }}>
          <Typography component="h2" variant="h2">
            React v2 preview
          </Typography>
          <Typography>
            Financial calculations remain in the FastAPI service and will not be
            reimplemented in the browser.
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button
              onClick={() => {
                setShowDetails((current) => !current);
              }}
              variant="outlined"
            >
              About this preview
            </Button>
            <Button
              onClick={() => {
                notify('Notifications are ready for migrated workflows.');
              }}
              variant="text"
            >
              Test notification
            </Button>
          </Stack>
          {showDetails ? (
            <Typography color="text.secondary">
              Appsmith remains available on port 8080 during migration. This
              shell stores no credentials or financial records.
            </Typography>
          ) : null}
        </Stack>
      </Paper>
    </Stack>
  );
}
