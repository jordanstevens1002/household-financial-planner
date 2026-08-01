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
import { selectionKeys } from '../../app/selectionStorage';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const account = {
  display_name: 'People Owner',
  email: null,
  global_role: 'USER',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'people-owner',
};
const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const household = {
  currency: 'NZD',
  display_name: 'Example household',
  id: householdId,
  jurisdiction: 'NZ',
};
const person = {
  date_of_birth: null,
  display_name: 'Alex Example',
  effective_from: '2026-08-02',
  effective_to: null,
  household_id: householdId,
  id: '85e30193-a324-4d22-9065-e25d819f6530',
  is_active: true,
  legal_name: null,
  notes: null,
  tax_jurisdiction: 'NZ',
  tax_residency_country: 'NZ',
};
const countries = [
  {
    code: 'AU',
    display_name: 'Australia',
    flag: '🇦🇺',
    recommended_currency: 'AUD',
  },
  {
    code: 'NZ',
    display_name: 'New Zealand',
    flag: '🇳🇿',
    recommended_currency: 'NZD',
  },
];

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
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
    history: createMemoryHistory({ initialEntries: ['/people'] }),
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
  await waitFor(() => expect(router.state.status).toBe('idle'), {
    timeout: 5000,
  });
}

function standardFetch(people: unknown = [person]) {
  return vi.fn<typeof fetch>((input) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(response({ account }));
    if (path.endsWith('/households'))
      return Promise.resolve(response([household]));
    if (path.endsWith('/people')) return Promise.resolve(response(people));
    if (path.endsWith('/reference/countries'))
      return Promise.resolve(response(countries));
    throw new Error(`Unexpected request: ${path}`);
  });
}

describe('household people workflows', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('requires a selected household before showing people', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households')) return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    await renderPage();

    expect(await screen.findByText('No household selected')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Add person' })).toBeNull();
  });

  it('restores only a person accessible in the selected household', async () => {
    localStorage.setItem(selectionKeys.household, householdId);
    localStorage.setItem(selectionKeys.person, person.id);
    vi.stubGlobal('fetch', standardFetch());

    await renderPage();

    expect(await screen.findByText('Alex Example')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Selected' })).toBeVisible();
    expect(localStorage.getItem(selectionKeys.person)).toBe(person.id);
    expect(screen.getByText(/records their identity only/i)).toBeVisible();
  });

  it('does not restore a saved person outside the selected household', async () => {
    localStorage.setItem(selectionKeys.household, householdId);
    localStorage.setItem(
      selectionKeys.person,
      '00000000-0000-0000-0000-000000000099',
    );
    vi.stubGlobal('fetch', standardFetch());

    await renderPage();

    expect(await screen.findByText('Alex Example')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Use person' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Selected' })).toBeNull();
  });

  it('returns to sign in when the people request reports an expired session', async () => {
    localStorage.setItem(selectionKeys.household, householdId);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/people'))
          return Promise.resolve(response({ detail: 'Session expired' }, 401));
        if (path.endsWith('/auth/status'))
          return Promise.resolve(response({ bootstrap_required: false }));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    await renderPage();

    expect(
      await screen.findByText(
        'Your session expired. Sign in again to continue.',
      ),
    ).toBeVisible();
  });

  it.each([403, 500])(
    'shows an HTTP %s people failure instead of an empty state',
    async (status) => {
      localStorage.setItem(selectionKeys.household, householdId);
      vi.stubGlobal(
        'fetch',
        vi.fn<typeof fetch>((input) => {
          const path = pathOf(input);
          if (path.endsWith('/auth/session'))
            return Promise.resolve(response({ account }));
          if (path.endsWith('/households'))
            return Promise.resolve(response([household]));
          if (path.endsWith('/people'))
            return Promise.resolve(
              response({ detail: `People request failed (${status})` }, status),
            );
          throw new Error(`Unexpected request: ${path}`);
        }),
      );

      await renderPage();

      expect(
        await screen.findByText(
          new RegExp(
            `Could not load people.*People request failed \\(${status}\\)`,
          ),
        ),
      ).toBeVisible();
      expect(screen.queryByText('No people recorded')).toBeNull();
    },
  );

  it('validates and creates a dated person using residency as jurisdiction', async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> | undefined;
    let created = false;
    localStorage.setItem(selectionKeys.household, householdId);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/reference/countries'))
          return Promise.resolve(response(countries));
        if (path.endsWith('/people') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          body = JSON.parse(init.body) as Record<string, unknown>;
          created = true;
          return Promise.resolve(response(person, 201));
        }
        if (path.endsWith('/people'))
          return Promise.resolve(response(created ? [person] : []));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    await renderPage();
    await user.click(await screen.findByRole('button', { name: 'Add person' }));
    await user.click(screen.getByRole('button', { name: 'Add person' }));
    expect(await screen.findByText('Enter a display name')).toBeVisible();

    await user.type(screen.getByLabelText('Display name'), 'Alex Example');
    await user.click(screen.getByLabelText('Tax residency (optional)'));
    await user.click(await screen.findByText('🇳🇿 New Zealand'));
    await user.click(screen.getByText('Advanced'));
    expect(screen.getByLabelText('Tax jurisdiction override')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Add person' }));

    await waitFor(() => expect(body).toBeDefined());
    expect(body).toMatchObject({
      display_name: 'Alex Example',
      tax_jurisdiction: 'NZ',
      tax_residency_country: 'NZ',
    });
    expect(localStorage.getItem(selectionKeys.person)).toBe(person.id);
    expect(await screen.findByText('Person added')).toBeVisible();
  });
});
