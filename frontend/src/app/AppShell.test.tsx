import { CssBaseline, ThemeProvider } from '@mui/material';
import {
  RouterProvider,
  createMemoryHistory,
  type AnyRouter,
} from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { NotificationProvider } from '../shared/NotificationProvider';
import {
  AuthContext,
  type AuthContextValue,
} from '../features/auth/AuthContext';
import { createAppRouter } from './router';
import { appTheme } from './theme';

async function renderRoute(path = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: [path] }),
  });

  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider client={queryClient}>
          <AuthContext.Provider value={authenticated}>
            <RouterProvider router={router as AnyRouter} />
          </AuthContext.Provider>
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
  await waitFor(
    () => {
      expect(router.state.status).toBe('idle');
    },
    { timeout: 5000 },
  );
}

const authenticated: AuthContextValue = {
  account: {
    display_name: 'Test User',
    email: null,
    global_role: 'USER',
    id: '00000000-0000-0000-0000-000000000001',
    must_change_password: false,
    username: 'test-user',
  },
  bootstrap: vi.fn(),
  changePassword: vi.fn(),
  csrfToken: vi.fn(),
  expired: false,
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

describe('application shell', () => {
  it('renders the overview and supports desktop navigation', async () => {
    const user = userEvent.setup();
    await renderRoute();

    expect(
      await screen.findByRole('heading', { name: 'Household overview' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Income & tax' })).toHaveAttribute(
      'href',
      '/income',
    );
    expect(
      screen.queryByRole('link', { name: 'User administration' }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole('link', { name: 'Properties' }));
    expect(
      await screen.findByRole('heading', { name: 'Properties' }),
    ).toBeInTheDocument();
    expect(screen.getByText('No household selected')).toBeInTheDocument();
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
