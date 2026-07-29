import { StrictMode } from 'react';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { createRoot } from 'react-dom/client';

import { queryClient } from './api/queryClient';
import { NotificationProvider } from './shared/NotificationProvider';
import { router } from './app/router';
import { appTheme } from './app/theme';

const root = document.getElementById('root');

if (root === null) {
  throw new Error('React root element was not found');
}

createRoot(root).render(
  <StrictMode>
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>
  </StrictMode>,
);
