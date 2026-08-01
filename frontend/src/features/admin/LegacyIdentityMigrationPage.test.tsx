import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  RouterProvider,
  createMemoryHistory,
  type AnyRouter,
} from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { createAppRouter } from '../../app/router';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const administrator = {
  created_at: '2026-07-30T00:00:00Z',
  display_name: 'Local Administrator',
  email: null,
  global_role: 'ADMIN',
  id: '00000000-0000-0000-0000-000000000001',
  is_active: true,
  must_change_password: false,
  password_expires_at: null,
  username: 'administrator',
} as const;

const legacyIdentity = {
  captured_at: '2026-07-30T00:00:00Z',
  display_name: 'Legacy Person',
  email: 'legacy@example.test',
  id: '00000000-0000-0000-0000-000000000020',
  mapping: null,
  memberships: [
    {
      household_id: '00000000-0000-0000-0000-000000000010',
      household_name: 'Personal household',
      role: 'OWNER',
    },
  ],
  oidc_subject: 'oidc|legacy-person',
  status: 'UNMAPPED',
} as const;

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
    history: createMemoryHistory({
      initialEntries: ['/administration/legacy-identities'],
    }),
  });
  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider
          client={
            new QueryClient({
              defaultOptions: { queries: { retry: false } },
            })
          }
        >
          <AuthProvider>
            <RouterProvider router={router as AnyRouter} />
          </AuthProvider>
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
  await waitFor(() => expect(router.state.status).toBe('idle'));
}

describe('legacy identity mapping wizard', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('does not request migration data for a non-administrator', async () => {
    let adminRequests = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(
            response({ account: { ...administrator, global_role: 'USER' } }),
          );
        }
        adminRequests += 1;
        return Promise.resolve(response({}));
      }),
    );

    await renderPage();
    expect(
      await screen.findByText(/global administrator account is required/i),
    ).toBeVisible();
    expect(adminRequests).toBe(0);
  });

  it('requires confirmation, creates an account, and shows its password once', async () => {
    const user = userEvent.setup();
    let mapBody: unknown;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(response({ account: administrator }));
        }
        if (path.endsWith('/admin/users')) {
          return Promise.resolve(response([administrator]));
        }
        if (path.endsWith('/mapping') && init?.method === 'POST') {
          if (typeof init.body !== 'string') {
            throw new Error('Expected a JSON request body');
          }
          mapBody = JSON.parse(init.body);
          return Promise.resolve(
            response(
              {
                identity: {
                  ...legacyIdentity,
                  mapping: {
                    application_user_id: '00000000-0000-0000-0000-000000000030',
                    display_name: 'Legacy Person',
                    id: '00000000-0000-0000-0000-000000000040',
                    last_reconciled_at: '2026-08-01T00:00:00Z',
                    mapped_at: '2026-08-01T00:00:00Z',
                    mapped_by_application_user_id: administrator.id,
                    username: 'legacy-local',
                  },
                  status: 'ACTIVATION_PENDING',
                },
                temporary_password: 'temporary-secret',
              },
              201,
            ),
          );
        }
        return Promise.resolve(
          response({
            activation_pending_count: 0,
            cutover_ready: false,
            identities: [legacyIdentity],
            unresolved_count: 1,
          }),
        );
      }),
    );

    await renderPage();
    await user.click(await screen.findByRole('button', { name: 'Map login' }));
    await user.click(screen.getByLabelText('Account target'));
    await user.click(
      screen.getByRole('option', { name: 'Create a new local account' }),
    );
    await user.type(screen.getByLabelText('Username'), 'legacy-local');
    await user.click(screen.getByRole('button', { name: 'Review mapping' }));
    expect(
      screen.getByRole('heading', { name: 'Confirm identity mapping' }),
    ).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Confirm mapping' }));

    expect(
      await screen.findByLabelText('One-time temporary password'),
    ).toHaveValue('temporary-secret');
    expect(mapBody).toEqual({
      new_account: {
        display_name: 'Legacy Person',
        email: 'legacy@example.test',
        username: 'legacy-local',
      },
    });
    await user.click(screen.getByRole('button', { name: 'I have saved it' }));
    await waitFor(() =>
      expect(
        screen.queryByLabelText('One-time temporary password'),
      ).not.toBeVisible(),
    );
  });

  it('reconciles and corrects an activation-pending mapping', async () => {
    const user = userEvent.setup();
    let mappingActive = true;
    let reconcileRequests = 0;
    const mappedIdentity = {
      ...legacyIdentity,
      mapping: {
        application_user_id: administrator.id,
        display_name: administrator.display_name,
        id: '00000000-0000-0000-0000-000000000040',
        last_reconciled_at: null,
        mapped_at: '2026-08-01T00:00:00Z',
        mapped_by_application_user_id: administrator.id,
        username: administrator.username,
      },
      status: 'ACTIVATION_PENDING',
    } as const;
    const currentList = () => ({
      activation_pending_count: mappingActive ? 1 : 0,
      cutover_ready: false,
      identities: [
        mappingActive ? mappedIdentity : { ...legacyIdentity, mapping: null },
      ],
      unresolved_count: 1,
    });
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session')) {
          return Promise.resolve(response({ account: administrator }));
        }
        if (path.endsWith('/admin/users')) {
          return Promise.resolve(response([administrator]));
        }
        if (path.endsWith('/reconcile') && init?.method === 'POST') {
          reconcileRequests += 1;
          return Promise.resolve(response(currentList()));
        }
        if (path.endsWith('/mapping') && init?.method === 'DELETE') {
          mappingActive = false;
          return Promise.resolve(response(null, 204));
        }
        return Promise.resolve(response(currentList()));
      }),
    );

    await renderPage();
    expect(
      await screen.findByText(/must complete password setup before cutover/i),
    ).toBeVisible();
    await user.click(
      screen.getByRole('button', { name: 'Reconcile memberships' }),
    );
    await waitFor(() => expect(reconcileRequests).toBe(1));
    await user.click(screen.getByRole('button', { name: 'Correct mapping' }));
    expect(
      screen.getByText(/removes access inherited through this mapping/i),
    ).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Revoke mapping' }));
    expect(
      await screen.findByRole('button', { name: 'Map login' }),
    ).toBeVisible();
  });
});
