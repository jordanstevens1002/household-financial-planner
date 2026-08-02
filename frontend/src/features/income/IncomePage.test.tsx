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

const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const personId = '85e30193-a324-4d22-9065-e25d819f6530';
const incomeTypeId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';
const account = {
  display_name: 'Income Owner',
  email: null,
  global_role: 'USER',
  id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
  must_change_password: false,
  username: 'income-owner',
};
const household = {
  currency: 'NZD',
  display_name: 'Income household',
  id: householdId,
  jurisdiction: 'NZ',
};
const person = {
  date_of_birth: null,
  display_name: 'Alex Income',
  effective_from: '2026-08-02',
  effective_to: null,
  household_id: householdId,
  id: personId,
  is_active: true,
  legal_name: null,
  notes: null,
  tax_jurisdiction: null,
  tax_residency_country: 'NZ',
};
const editorAccess = {
  can_administer: false,
  can_edit: true,
  can_manage_owners: false,
  can_view: true,
  role: 'EDITOR',
};
const income = {
  annual_growth_rate: null,
  display_name: 'Salary',
  effective_from: '2026-08-02',
  effective_to: null,
  frequency: 'MONTHLY',
  gross_amount: '5000.00',
  id: '6ace21c6-058c-4f42-af75-d2eb55da6077',
  income_type_id: incomeTypeId,
  notes: null,
  person_id: personId,
  salary_sacrifice_amount: null,
  taxable: true,
};

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
    history: createMemoryHistory({ initialEntries: ['/income'] }),
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

function standardFetch(
  incomes: unknown = [income],
  access: unknown = editorAccess,
) {
  return vi.fn<typeof fetch>((input) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(response({ account }));
    if (path.endsWith('/households'))
      return Promise.resolve(response([household]));
    if (path.endsWith('/people')) return Promise.resolve(response([person]));
    if (path.endsWith('/access')) return Promise.resolve(response(access));
    if (path.endsWith('/income-sources'))
      return Promise.resolve(
        incomes instanceof Response ? incomes : response(incomes),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
}

describe('person income workflows', () => {
  beforeEach(() => {
    localStorage.setItem(selectionKeys.household, householdId);
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('requires a person selected from the current household', async () => {
    vi.stubGlobal('fetch', standardFetch());

    await renderPage();

    expect(await screen.findByText('No person selected')).toBeVisible();
    expect(
      screen.getByRole('link', { name: 'Choose a person' }),
    ).toHaveAttribute('href', '/people');
  });

  it('lets a viewer read income without offering creation', async () => {
    localStorage.setItem(selectionKeys.person, personId);
    vi.stubGlobal(
      'fetch',
      standardFetch([income], {
        ...editorAccess,
        can_edit: false,
        role: 'VIEWER',
      }),
    );

    await renderPage();

    const table = await screen.findByRole('table', { name: 'Income sources' });
    expect(within(table).getByText('Salary')).toBeVisible();
    expect(screen.getByText(/view-only access/i)).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Add income source' }),
    ).toBeNull();
  });

  it('shows an income request failure instead of an empty state', async () => {
    localStorage.setItem(selectionKeys.person, personId);
    vi.stubGlobal(
      'fetch',
      standardFetch(response({ detail: 'Income unavailable' }, 500)),
    );

    await renderPage();

    expect(
      await screen.findByText(/Could not load income sources/i),
    ).toBeVisible();
    expect(screen.queryByText('No income sources yet')).toBeNull();
  });

  it('validates and creates a dated recurring income source', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    localStorage.setItem(selectionKeys.person, personId);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/people'))
          return Promise.resolve(response([person]));
        if (path.endsWith('/access'))
          return Promise.resolve(response(editorAccess));
        if (path.endsWith('/lookups/income_type'))
          return Promise.resolve(
            response([
              {
                category: 'income_type',
                code: 'SALARY',
                display_name: 'Salary or wages',
                id: incomeTypeId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith('/income-sources') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(response(income, 201));
        }
        if (path.endsWith('/income-sources'))
          return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add income source' }),
    );
    await user.click(screen.getByRole('button', { name: 'Add income source' }));
    expect(await screen.findByText('Enter a name')).toBeVisible();

    await user.click(screen.getByLabelText('Income type'));
    await user.click(await screen.findByText('Salary or wages'));
    await user.type(screen.getByLabelText('Income name'), 'Salary');
    await user.type(screen.getByLabelText('Gross amount'), '5000');
    await user.click(screen.getByText('Advanced'));
    expect(screen.getByLabelText('Annual growth % (optional)')).toBeVisible();
    await user.type(screen.getByLabelText('Annual growth % (optional)'), '3');
    await user.click(screen.getByRole('button', { name: 'Add income source' }));

    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody).toMatchObject({
      annual_growth_rate: '3',
      display_name: 'Salary',
      frequency: 'MONTHLY',
      gross_amount: '5000',
      income_type_id: incomeTypeId,
      taxable: true,
    });
    expect(await screen.findByText('Income source added')).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(screen.getByRole('table', { name: 'Income sources' })).toBeVisible();
  });
});
