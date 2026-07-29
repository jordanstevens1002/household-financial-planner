import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Container,
  CssBaseline,
  Paper,
  Stack,
  ThemeProvider,
  Typography,
  createTheme,
} from '@mui/material';

const theme = createTheme({
  palette: {
    primary: {
      main: '#315b4c',
    },
    background: {
      default: '#f4f7f5',
    },
  },
  typography: {
    fontFamily: '"Inter", "Segoe UI", sans-serif',
  },
});

export function App() {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box component="main" sx={{ minHeight: '100vh', py: 10 }}>
        <Container maxWidth="md">
          <Paper elevation={0} sx={{ border: 1, borderColor: 'divider', p: 6 }}>
            <Stack spacing={3}>
              <Typography component="h1" variant="h3">
                Household Financial Planner
              </Typography>
              <Typography color="text.secondary" variant="h6">
                React v2 foundation
              </Typography>
              <Alert severity="info">
                The new interface is being built alongside the current
                application. Financial workflows will appear here as each tested
                migration slice is completed.
              </Alert>
              <Button
                onClick={() => {
                  setShowDetails((current) => !current);
                }}
                sx={{ alignSelf: 'flex-start' }}
                variant="outlined"
              >
                About this preview
              </Button>
              {showDetails ? (
                <Typography>
                  Appsmith remains available during the migration. This preview
                  does not store credentials or household information.
                </Typography>
              ) : null}
            </Stack>
          </Paper>
        </Container>
      </Box>
    </ThemeProvider>
  );
}
