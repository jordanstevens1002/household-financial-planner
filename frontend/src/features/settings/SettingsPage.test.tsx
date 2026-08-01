import { ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { appTheme } from '../../app/theme';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import { SettingsPage } from './SettingsPage';

const auth: AuthContextValue = {
  account: {
    display_name: 'Settings Owner',
    email: null,
    global_role: 'ADMIN',
    id: '00000000-0000-0000-0000-000000000001',
    must_change_password: false,
    username: 'settings-owner',
  },
  bootstrap: vi.fn(),
  changePassword: vi.fn(),
  csrfToken: vi.fn(),
  expired: false,
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

function response(body: unknown, status = 200, requestId?: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (requestId) headers['X-Request-ID'] = requestId;
  return new Response(JSON.stringify(body), { headers, status });
}

function pathOf(input: RequestInfo | URL) {
  return typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.href
      : input.url;
}

function renderPage() {
  render(
    <ThemeProvider theme={appTheme}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <AuthContext.Provider value={auth}>
          <SettingsPage />
        </AuthContext.Provider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('settings and installation metadata', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows health, session, reference catalogues and installed providers', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/health/live'))
          return Promise.resolve(response({ status: 'ok', version: '1.0.0' }));
        if (path.endsWith('/health/ready'))
          return Promise.resolve(response({ status: 'ready' }));
        if (path.endsWith('/reference/countries'))
          return Promise.resolve(
            response([
              {
                code: 'NZ',
                display_name: 'New Zealand',
                flag: '🇳🇿',
                recommended_currency: 'NZD',
              },
            ]),
          );
        if (path.endsWith('/reference/currencies'))
          return Promise.resolve(
            response([
              {
                code: 'NZD',
                display_name: 'New Zealand Dollar',
                numeric_code: '554',
              },
            ]),
          );
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(
            response([
              {
                display_name: 'Example tax',
                jurisdiction: 'EX',
                supported_tax_years: ['2026'],
              },
            ]),
          );
        if (path.endsWith('/retirement-providers'))
          return Promise.resolve(
            response([
              { code: 'EX_RETIRE', display_name: 'Example retirement' },
            ]),
          );
        if (path.endsWith('/purchase-providers'))
          return Promise.resolve(
            response([{ code: 'EX_BUY', display_name: 'Example purchase' }]),
          );
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPage();

    expect(await screen.findByText('API available')).toBeVisible();
    expect(screen.getByText('Database ready')).toBeVisible();
    expect(screen.getByText('Application version: 1.0.0')).toBeVisible();
    expect(screen.getByText('Account: Settings Owner')).toBeVisible();
    const providers = screen.getByRole('table', {
      name: 'Installed financial providers',
    });
    expect(within(providers).getByText('Example tax')).toBeVisible();
    expect(within(providers).getByText('Example retirement')).toBeVisible();
    expect(within(providers).getByText('Example purchase')).toBeVisible();

    await user.click(screen.getByText('Advanced'));
    expect(
      screen.getByText('1 countries and 1 currencies available'),
    ).toBeVisible();
    await user.click(screen.getByLabelText('Browse countries'));
    expect(await screen.findByText('🇳🇿 New Zealand')).toBeVisible();
  });

  it('reports failed installation checks with their request ID', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/health/ready'))
          return Promise.resolve(
            response(
              { detail: 'Database unavailable' },
              503,
              'settings-request',
            ),
          );
        if (path.endsWith('/health/live'))
          return Promise.resolve(response({ status: 'ok', version: '1.0.0' }));
        return Promise.resolve(response([]));
      }),
    );

    renderPage();

    expect(
      await screen.findByText(
        'Database readiness: Database unavailable (request settings-request)',
      ),
    ).toBeVisible();
    expect(screen.getByText('Database unavailable')).toBeVisible();
  });
});
