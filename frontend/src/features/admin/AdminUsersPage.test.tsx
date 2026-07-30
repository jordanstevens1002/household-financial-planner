import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  RouterProvider,
  createMemoryHistory,
  type AnyRouter,
} from '@tanstack/react-router';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { createAppRouter } from '../../app/router';
import { appTheme } from '../../app/theme';
import type { components } from '../../api/schema';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const administrator = {
  display_name: 'Local Administrator',
  email: null,
  global_role: 'ADMIN',
  id: '00000000-0000-0000-0000-000000000001',
  is_active: true,
  must_change_password: false,
  password_expires_at: null,
  created_at: '2026-07-30T00:00:00Z',
  username: 'administrator',
} as const;
type AdminUser = components['schemas']['AdminUserResponse'];

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

async function renderPage() {
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/administration'] }),
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router as AnyRouter} />
          </AuthProvider>
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
  await waitFor(() => expect(router.state.status).toBe('idle'));
}

describe('local user administration', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not treat an ordinary account as a global administrator', async () => {
    let adminRequests = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(
            response({
              account: { ...administrator, global_role: 'USER' },
            }),
          );
        }
        adminRequests += 1;
        return Promise.resolve(response([]));
      }),
    );
    await renderPage();

    expect(
      await screen.findByText(/household roles do not grant access here/i),
    ).toBeVisible();
    expect(adminRequests).toBe(0);
  });

  it('creates a user and shows the temporary password only once', async () => {
    const user = userEvent.setup();
    const users: AdminUser[] = [administrator];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(response({ account: administrator }));
        }
        if (path.endsWith('/admin/users') && init?.method === 'POST') {
          const created = {
            ...administrator,
            display_name: 'Review User',
            global_role: 'USER',
            id: '00000000-0000-0000-0000-000000000002',
            must_change_password: true,
            username: 'review-user',
          } as const;
          users.push(created);
          return Promise.resolve(
            response(
              {
                account: created,
                temporary_password: 'one-time-password',
              },
              201,
            ),
          );
        }
        return Promise.resolve(response(users));
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add user' }));
    await user.type(screen.getByLabelText('Username'), 'review-user');
    await user.type(screen.getByLabelText('Display name'), 'Review User');
    await user.click(screen.getByRole('button', { name: 'Create user' }));
    expect(await screen.findByDisplayValue('one-time-password')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'I have saved it' }));
    expect(
      screen.queryByDisplayValue('one-time-password'),
    ).not.toBeInTheDocument();
    expect(await screen.findByText('review-user')).toBeVisible();
  });

  it('confirms self-demotion and explains the recovery safeguard', async () => {
    const user = userEvent.setup();
    let submitted: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(response({ account: administrator }));
        }
        if (init?.method === 'PATCH') {
          submitted = JSON.parse(
            typeof init.body === 'string' ? init.body : '{}',
          ) as Record<string, unknown>;
          return Promise.resolve(
            response(
              { detail: 'Another recovery-capable administrator is required' },
              409,
            ),
          );
        }
        return Promise.resolve(response([administrator]));
      }),
    );
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Change to user' }),
    );
    const dialog = screen.getByRole('dialog', {
      name: 'Confirm account change',
    });
    expect(
      within(dialog).getByText(
        /another administrator has completed password setup/i,
      ),
    ).toBeVisible();
    await user.click(
      within(dialog).getByRole('button', { name: 'Change role' }),
    );
    expect(
      await screen.findByText(
        'Another recovery-capable administrator is required',
      ),
    ).toBeVisible();
    expect(submitted).toMatchObject({
      confirm_self_lockout: true,
      global_role: 'USER',
    });
  });

  it('returns a one-time reset path after confirmation', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(response({ account: administrator }));
        }
        if (path.endsWith('/password-reset') && init?.method === 'POST') {
          return Promise.resolve(
            response({
              expires_at: '2026-07-30T00:30:00Z',
              reset_path: '/reset-password?token=one-use-token',
            }),
          );
        }
        return Promise.resolve(response([administrator]));
      }),
    );
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Reset password' }),
    );
    await user.click(
      screen.getByRole('button', { name: 'Generate reset path' }),
    );
    expect(
      await screen.findByDisplayValue(/\/reset-password\?token=one-use-token$/),
    ).toBeVisible();
  });

  it('promotes, disables and re-enables an account', async () => {
    const user = userEvent.setup();
    const member: AdminUser = {
      ...administrator,
      display_name: 'Household Member',
      global_role: 'USER',
      id: '00000000-0000-0000-0000-000000000003',
      username: 'household-member',
    };
    const users: AdminUser[] = [administrator, member];
    const updates: Array<Record<string, unknown>> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(response({ account: administrator }));
        }
        if (init?.method === 'PATCH') {
          const payload = JSON.parse(
            typeof init.body === 'string' ? init.body : '{}',
          ) as Record<string, unknown>;
          updates.push(payload);
          Object.assign(member, payload);
          return Promise.resolve(response(member));
        }
        return Promise.resolve(response(users));
      }),
    );
    await renderPage();

    let row = (await screen.findByText('household-member')).closest('tr');
    expect(row).not.toBeNull();
    await user.click(
      within(row!).getByRole('button', { name: 'Make administrator' }),
    );
    await waitFor(() => expect(updates).toHaveLength(1));

    row = screen.getByText('household-member').closest('tr');
    await user.click(within(row!).getByRole('button', { name: 'Disable' }));
    await user.click(screen.getByRole('button', { name: 'Disable account' }));
    await waitFor(() => expect(updates).toHaveLength(2));

    await user.click(await screen.findByRole('button', { name: 'Enable' }));
    await waitFor(() => expect(updates).toHaveLength(3));
    expect(updates).toEqual([
      { confirm_self_lockout: false, global_role: 'ADMIN' },
      { confirm_self_lockout: false, is_active: false },
      { confirm_self_lockout: false, is_active: true },
    ]);
  });
});
