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
import { selectionKeys } from '../../app/selectionStorage';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const account = {
  display_name: 'Household Owner',
  email: null,
  global_role: 'USER',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'owner',
};
const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const household = {
  currency: 'AUD',
  display_name: 'Home household',
  id: householdId,
  jurisdiction: 'AU',
};
const owner = {
  application_user_id: account.id,
  display_name: account.display_name,
  household_id: householdId,
  id: '00000000-0000-0000-0000-000000000020',
  is_active: true,
  role: 'OWNER',
  username: account.username,
};

function response(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status,
  });
}

function pathOf(input: RequestInfo | URL) {
  return typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.href
      : input.url;
}

async function renderPage() {
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/households'] }),
  });
  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
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

describe('household selection and membership', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('restores an accessible selection after session validation', async () => {
    localStorage.setItem(selectionKeys.household, householdId);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/memberships'))
          return Promise.resolve(response([owner]));
        if (path.endsWith('/reference/countries'))
          return Promise.resolve(response([]));
        if (path.endsWith('/reference/currencies'))
          return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    await renderPage();

    expect(await screen.findByText('Home household members')).toBeVisible();
    expect(localStorage.getItem(selectionKeys.household)).toBe(householdId);
  });

  it('clears an inaccessible selection and dependent selections', async () => {
    localStorage.setItem(
      selectionKeys.household,
      '85e30193-a324-4d22-9065-e25d819f6530',
    );
    localStorage.setItem(selectionKeys.person, account.id);
    localStorage.setItem(selectionKeys.property, householdId);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        return Promise.resolve(response([]));
      }),
    );
    await renderPage();

    await waitFor(() => {
      expect(localStorage.getItem(selectionKeys.household)).toBeNull();
    });
    expect(localStorage.getItem(selectionKeys.person)).toBeNull();
    expect(localStorage.getItem(selectionKeys.property)).toBeNull();
  });

  it('keeps household selection available without membership administration', async () => {
    localStorage.setItem(selectionKeys.household, householdId);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/memberships'))
          return Promise.resolve(
            response({ detail: 'Household administrator role required' }, 403),
          );
        return Promise.resolve(response([]));
      }),
    );
    await renderPage();

    expect(
      await screen.findByText(
        /only household owners and administrators can manage memberships/i,
      ),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Selected' })).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Add member' }),
    ).not.toBeInTheDocument();
  });

  it('creates, selects, and manages a household member', async () => {
    const user = userEvent.setup();
    const households = [household];
    const members = [owner];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/reference/countries'))
          return Promise.resolve(
            response([{ code: 'NZ', display_name: 'New Zealand', flag: '🇳🇿' }]),
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
        if (path.endsWith('/households') && init?.method === 'POST') {
          const created = {
            currency: 'NZD',
            display_name: 'Future household',
            id: '5d5b7d5c-f8c0-4599-bebf-3ed219d9209e',
            jurisdiction: 'NZ',
          };
          households.push(created);
          return Promise.resolve(response(created, 201));
        }
        if (path.endsWith('/households'))
          return Promise.resolve(response(households));
        if (path.endsWith('/memberships') && init?.method === 'POST') {
          const added = {
            ...owner,
            application_user_id: '00000000-0000-0000-0000-000000000002',
            display_name: 'Taylor',
            id: '00000000-0000-0000-0000-000000000021',
            role: 'VIEWER',
            username: 'taylor',
          };
          members.push(added);
          return Promise.resolve(response(added, 201));
        }
        if (path.endsWith('/memberships'))
          return Promise.resolve(response(members));
        return Promise.resolve(response({}, 404));
      }),
    );
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Use household' }),
    );
    await user.click(screen.getByRole('button', { name: 'Add member' }));
    await user.type(screen.getByLabelText('Local account username'), 'taylor');
    await user.click(screen.getByRole('button', { name: 'Add member' }));
    expect(await screen.findByText('Taylor')).toBeVisible();
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Add household member' }),
      ).not.toBeInTheDocument(),
    );

    await user.click(screen.getByRole('button', { name: 'Create household' }));
    await user.type(
      screen.getByLabelText('Household name'),
      'Future household',
    );
    await user.click(screen.getByLabelText('Country'));
    await user.click(await screen.findByText('🇳🇿 New Zealand'));
    await user.click(screen.getByLabelText('Currency'));
    await user.click(await screen.findByText('NZD — New Zealand Dollar'));
    await user.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Create household' }),
      ).not.toBeInTheDocument(),
    );
    const table = await screen.findByRole('table', { name: 'Your households' });
    expect(within(table).getByText('Future household')).toBeVisible();
  }, 10_000);
});
