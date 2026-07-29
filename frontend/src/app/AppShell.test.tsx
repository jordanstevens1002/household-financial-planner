import { CssBaseline, ThemeProvider } from '@mui/material';
import {
  RouterProvider,
  createMemoryHistory,
  type AnyRouter,
} from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { NotificationProvider } from '../shared/NotificationProvider';
import { createAppRouter } from './router';
import { appTheme } from './theme';

async function renderRoute(path = '/') {
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: [path] }),
  });

  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <RouterProvider router={router as AnyRouter} />
      </NotificationProvider>
    </ThemeProvider>,
  );
  await waitFor(() => {
    expect(router.state.status).toBe('idle');
  });
}

describe('application shell', () => {
  it('renders the overview and supports desktop navigation', async () => {
    const user = userEvent.setup();
    await renderRoute();

    expect(
      await screen.findByRole('heading', { name: 'Household overview' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('navigation')).toBeInTheDocument();

    await user.click(screen.getByRole('link', { name: 'Properties' }));
    expect(
      await screen.findByRole('heading', {
        name: 'Properties is coming next',
      }),
    ).toBeInTheDocument();
  });

  it('shows preview details and notifications', async () => {
    const user = userEvent.setup();
    await renderRoute();

    await user.click(
      await screen.findByRole('button', { name: 'About this preview' }),
    );
    expect(screen.getByText(/Appsmith remains available/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Test notification' }));
    expect(
      await screen.findByText(/Notifications are ready/i),
    ).toBeInTheDocument();
  });

  it('renders a useful not-found route', async () => {
    await renderRoute('/missing');

    expect(
      await screen.findByRole('heading', { name: 'Page not found' }),
    ).toBeInTheDocument();
  });
});
