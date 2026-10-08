import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AnyRouter } from '@tanstack/react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createAppRouter } from '../../app/router';
import { selectionKeys } from '../../app/selectionStorage';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const householdId = '10000000-0000-4000-8000-000000000001';
const accountTypeId = '10000000-0000-4000-8000-000000000002';
const personId = '10000000-0000-4000-8000-000000000003';
const account = {
  account_type_id: accountTypeId,
  annual_fees: '120.00',
  currency: 'AUD',
  display_name: 'Future fund',
  expected_return_rate: '6.0000',
  household_id: householdId,
  id: '10000000-0000-4000-8000-000000000004',
  is_active: true,
  notes: null,
  opening_balance: '100000.00',
  opening_balance_date: '2026-01-01',
  person_id: personId,
  provider_code: null,
  provider_settings: {},
  retirement_age: 67,
};
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status,
  });
const pathOf = (input: RequestInfo | URL) =>
  typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.href
      : input.url;

function fetcher(canEdit = true, accounts: unknown[] = [account]) {
  return vi.fn<typeof fetch>((input, init) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(
        response({
          account: {
            display_name: 'Owner',
            global_role: 'USER',
            id: '00000000-0000-0000-0000-000000000001',
            must_change_password: false,
            username: 'owner',
          },
        }),
      );
    if (path.endsWith('/households'))
      return Promise.resolve(
        response([
          {
            currency: 'AUD',
            display_name: 'Home',
            id: householdId,
            jurisdiction: 'AU',
          },
        ]),
      );
    if (path.endsWith('/access'))
      return Promise.resolve(
        response({
          can_administer: canEdit,
          can_edit: canEdit,
          can_manage_owners: false,
          can_view: true,
          role: canEdit ? 'EDITOR' : 'VIEWER',
        }),
      );
    if (path.endsWith('/people'))
      return Promise.resolve(
        response([
          {
            display_name: 'Alex',
            effective_from: '2020-01-01',
            effective_to: null,
            household_id: householdId,
            id: personId,
            is_active: true,
          },
        ]),
      );
    if (path.endsWith('/lookups/retirement_account_type'))
      return Promise.resolve(
        response([
          {
            category: 'retirement_account_type',
            code: 'GENERIC',
            display_name: 'Retirement savings',
            id: accountTypeId,
            is_active: true,
          },
        ]),
      );
    if (path.endsWith('/retirement-providers'))
      return Promise.resolve(
        response([
          { code: 'AU_SUPER', display_name: 'Australian superannuation' },
        ]),
      );
    if (path.endsWith('/reference/currencies'))
      return Promise.resolve(
        response([{ code: 'AUD', name: 'Australian Dollar' }]),
      );
    if (path.endsWith('/retirement-accounts') && init?.method === 'POST')
      return Promise.resolve(response(account, 201));
    if (path.endsWith('/retirement-accounts'))
      return Promise.resolve(response(accounts));
    throw new Error(`Unexpected request: ${path}`);
  });
}

async function renderPage() {
  localStorage.setItem(selectionKeys.household, householdId);
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/retirement'] }),
  });
  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider client={new QueryClient()}>
          <AuthProvider>
            <RouterProvider router={router as AnyRouter} />
          </AuthProvider>
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
  await waitFor(() => expect(router.state.status).toBe('idle'));
}

describe('retirement account catalogue', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('lists country-neutral account details', async () => {
    vi.stubGlobal('fetch', fetcher());
    await renderPage();

    expect(await screen.findByText('Future fund')).toBeVisible();
    expect(screen.getByText('Alex')).toBeVisible();
    expect(screen.getByText('Retirement savings')).toBeVisible();
    expect(screen.getByText('A$100,000.00')).toBeVisible();
  });

  it('creates an account with optional provider settings', async () => {
    const user = userEvent.setup();
    const mock = fetcher(true, []);
    vi.stubGlobal('fetch', mock);
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add account' }),
    );
    const dialog = await screen.findByRole('dialog', {
      name: 'Add retirement account',
    });
    await user.type(
      within(dialog).getByLabelText('Account name'),
      'My account',
    );
    await user.click(within(dialog).getByLabelText('Account type'));
    await user.click(await screen.findByText('Retirement savings'));
    await user.click(
      within(dialog).getByLabelText('Installed provider (optional)'),
    );
    await user.click(await screen.findByText('Australian superannuation'));
    await user.click(within(dialog).getByText('Advanced'));
    fireEvent.change(
      within(dialog).getByLabelText('Provider settings (JSON)'),
      {
        target: { value: '{"preservation_age":60}' },
      },
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Save account' }),
    );

    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith('/retirement-accounts') &&
            init?.method === 'POST' &&
            typeof init.body === 'string' &&
            init.body.includes('AU_SUPER'),
        ),
      ).toBe(true),
    );
  });

  it('keeps creation unavailable to viewers', async () => {
    vi.stubGlobal('fetch', fetcher(false, []));
    await renderPage();
    expect(await screen.findByText(/view-only access/i)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Add account' })).toBeNull();
  });
});
