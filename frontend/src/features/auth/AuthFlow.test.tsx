import { CssBaseline, ThemeProvider } from '@mui/material';
import {
  RouterProvider,
  createMemoryHistory,
  type AnyRouter,
} from '@tanstack/react-router';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { apiRequest } from '../../api/client';
import { createAppRouter } from '../../app/router';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from './AuthProvider';

const account = {
  display_name: 'Local Administrator',
  email: null,
  global_role: 'ADMIN',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'administrator',
};

function response(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status,
  });
}

function pathOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  return input instanceof URL ? input.href : input.url;
}

async function renderApplication(path = '/') {
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <AuthProvider>
          <RouterProvider router={router as AnyRouter} />
        </AuthProvider>
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

describe('local authentication flow', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('bootstraps the first administrator without persisting credentials', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/session')) {
          return Promise.resolve(
            response({ detail: 'Authentication required' }, 401),
          );
        }
        if (path.endsWith('/status')) {
          return Promise.resolve(response({ bootstrap_required: true }));
        }
        expect(new Headers(init?.headers).get('X-Bootstrap-Token')).toBe(
          'operator-bootstrap-token-value',
        );
        return Promise.resolve(
          response({ account, csrf_token: 'csrf-value' }, 201),
        );
      }),
    );
    await renderApplication();

    expect(
      await screen.findByRole('heading', {
        name: 'Create the first administrator',
      }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText('Username'), 'administrator');
    await user.type(
      screen.getByLabelText('Bootstrap token'),
      'operator-bootstrap-token-value',
    );
    await user.type(screen.getByLabelText('Password'), 'secret');
    await user.click(
      screen.getByRole('button', { name: 'Create administrator' }),
    );

    expect(
      await screen.findByRole('heading', { name: 'Household overview' }),
    ).toBeInTheDocument();
    expect(localStorage).toHaveLength(0);
  });

  it('preserves username after failure and restores the requested route', async () => {
    const user = userEvent.setup();
    let loginAttempts = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/session')) {
          return Promise.resolve(
            response({ detail: 'Authentication required' }, 401),
          );
        }
        if (path.endsWith('/status')) {
          return Promise.resolve(response({ bootstrap_required: false }));
        }
        loginAttempts += 1;
        return Promise.resolve(
          loginAttempts === 1
            ? response({ detail: 'Invalid username or password' }, 401)
            : response({ account, csrf_token: 'csrf-value' }),
        );
      }),
    );
    await renderApplication('/retirement');

    await user.type(await screen.findByLabelText('Username'), 'administrator');
    await user.type(screen.getByLabelText('Password'), 'incorrect password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(
      await screen.findByText('Invalid username or password'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Username')).toHaveValue('administrator');
    expect(screen.getByLabelText('Password')).toHaveValue('');

    await user.type(
      screen.getByLabelText('Password'),
      'correct horse battery staple',
    );
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(
      await screen.findByRole('heading', { name: 'Retirement is coming soon' }),
    ).toBeInTheDocument();
  });

  it('requires a temporary password to be changed before entry', async () => {
    const user = userEvent.setup();
    let changeAttempts = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/session')) {
          return Promise.resolve(
            response({
              account: { ...account, must_change_password: true },
            }),
          );
        }
        changeAttempts += 1;
        return Promise.resolve(
          changeAttempts === 1
            ? response({ detail: 'Current password is incorrect' }, 401)
            : response({ account }),
        );
      }),
    );
    await renderApplication();

    expect(
      await screen.findByRole('heading', { name: 'Choose a new password' }),
    ).toBeInTheDocument();
    await user.type(
      screen.getByLabelText('Temporary password'),
      'temporary password',
    );
    await user.type(
      screen.getByLabelText('New password'),
      'replacement password',
    );
    await user.type(
      screen.getByLabelText('Confirm new password'),
      'replacement password',
    );
    await user.click(screen.getByRole('button', { name: 'Save password' }));
    expect(
      await screen.findByText('Current password is incorrect'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Choose a new password' }),
    ).toBeInTheDocument();

    await user.type(
      screen.getByLabelText('Temporary password'),
      'temporary password',
    );
    await user.type(
      screen.getByLabelText('New password', { exact: true }),
      'replacement password',
    );
    await user.type(
      screen.getByLabelText('Confirm new password'),
      'replacement password',
    );
    await user.click(screen.getByRole('button', { name: 'Save password' }));
    expect(
      await screen.findByRole('heading', { name: 'Household overview' }),
    ).toBeInTheDocument();
  });

  it('logs out and returns to the login form', async () => {
    const user = userEvent.setup();
    let sessionActive = true;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/session') && sessionActive) {
          return Promise.resolve(response({ account }));
        }
        if (path.endsWith('/logout')) {
          sessionActive = false;
          return Promise.resolve(response(null, 204));
        }
        if (path.endsWith('/status')) {
          return Promise.resolve(response({ bootstrap_required: false }));
        }
        return Promise.resolve(
          response({ detail: 'Authentication required' }, 401),
        );
      }),
    );
    await renderApplication();

    await user.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(
      await screen.findByRole('heading', { name: 'Sign in' }),
    ).toBeInTheDocument();
  });

  it('reports expiry when later API activity rejects an active session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        if (pathOf(input).endsWith('/session')) {
          return Promise.resolve(response({ account }));
        }
        return Promise.resolve(
          response({ detail: 'Session expired or invalid' }, 401),
        );
      }),
    );
    await renderApplication();
    expect(
      await screen.findByRole('heading', { name: 'Household overview' }),
    ).toBeInTheDocument();

    await act(async () => {
      await apiRequest('/api/v1/households').catch(() => undefined);
    });
    expect(
      await screen.findByText(
        'Your session expired. Sign in again to continue.',
      ),
    ).toBeInTheDocument();
  });

  it('consumes a single-use password reset path', async () => {
    const user = userEvent.setup();
    let submitted: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        if (pathOf(input).endsWith('/password/reset')) {
          submitted = JSON.parse(
            typeof init?.body === 'string' ? init.body : '{}',
          ) as Record<string, unknown>;
          return Promise.resolve(response(null, 204));
        }
        return Promise.resolve(
          response({ detail: 'Authentication required' }, 401),
        );
      }),
    );
    await renderApplication('/reset-password#token=single-use-value');

    expect(window.location.pathname).toBe('/reset-password');
    expect(window.location.hash).toBe('');

    await user.type(
      await screen.findByLabelText('New password'),
      'replacement',
    );
    await user.type(
      screen.getByLabelText('Confirm new password'),
      'replacement',
    );
    await user.click(screen.getByRole('button', { name: 'Reset password' }));
    expect(
      await screen.findByRole('heading', { name: 'Password updated' }),
    ).toBeVisible();
    expect(submitted).toEqual({
      new_password: 'replacement',
      token: 'single-use-value',
    });
  });
});
