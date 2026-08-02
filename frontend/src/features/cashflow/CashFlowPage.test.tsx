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
import { expenseSchema } from './expenseValidation';

const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const personId = '85e30193-a324-4d22-9065-e25d819f6530';
const categoryId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';
const account = {
  display_name: 'Cash-flow Owner',
  email: null,
  global_role: 'USER',
  id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
  must_change_password: false,
  username: 'cashflow-owner',
};
const household = {
  currency: 'NZD',
  display_name: 'Cash-flow household',
  id: householdId,
  jurisdiction: 'NZ',
};
const expense = {
  amount: '125.50',
  annual_growth_rate: null,
  category_id: categoryId,
  display_name: 'Groceries',
  effective_from: '2026-08-02',
  effective_to: null,
  frequency: 'WEEKLY',
  household_id: householdId,
  id: '6ace21c6-058c-4f42-af75-d2eb55da6077',
  is_essential: true,
  notes: null,
  person_id: null,
};
const editorAccess = {
  can_administer: false,
  can_edit: true,
  can_manage_owners: false,
  can_view: true,
  role: 'EDITOR',
};
const emptyCashflow = {
  annual_expenses: '0.00',
  annual_gross_income: '0.00',
  annual_loan_repayments: '0.00',
  annual_net_income: '0.00',
  annual_ordinary_expenses: '0.00',
  annual_surplus: '0.00',
  as_of: '2026-08-02',
  currency: 'NZD',
  household_id: householdId,
  loan_repayments: [],
  monthly_expenses: '0.00',
  monthly_loan_repayments: '0.00',
  monthly_net_income: '0.00',
  monthly_ordinary_expenses: '0.00',
  monthly_surplus: '0.00',
  people: [],
  warnings: [],
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
    history: createMemoryHistory({ initialEntries: ['/cash-flow'] }),
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
    timeout: 10_000,
  });
}

function standardFetch(
  expenses: unknown = [expense],
  access: unknown = editorAccess,
) {
  return vi.fn<typeof fetch>((input) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(response({ account }));
    if (path.endsWith('/households'))
      return Promise.resolve(response([household]));
    if (path.endsWith('/expenses')) return Promise.resolve(response(expenses));
    if (path.endsWith('/access')) return Promise.resolve(response(access));
    if (path.endsWith('/lookups/household_expense_type'))
      return Promise.resolve(
        response([
          {
            category: 'household_expense_type',
            code: 'UTILITIES',
            display_name: 'Utilities',
            id: categoryId,
            is_active: true,
          },
        ]),
      );
    if (path.endsWith('/people')) return Promise.resolve(response([]));
    if (path.includes('/cashflow?'))
      return Promise.resolve(response(emptyCashflow));
    throw new Error(`Unexpected request: ${path}`);
  });
}

describe('household expense workflows', () => {
  beforeEach(() => {
    localStorage.setItem(selectionKeys.household, householdId);
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('lists dated expenses with household currency context', async () => {
    vi.stubGlobal('fetch', standardFetch());
    await renderPage();

    const table = await screen.findByRole('table', {
      name: 'Household expenses',
    });
    expect(table).toHaveTextContent('Groceries');
    expect(table).toHaveTextContent('NZ$125.50');
    expect(table).toHaveTextContent('Weekly');
    expect(table).toHaveTextContent('Utilities');
    expect(table).toHaveTextContent('Whole household');
    expect(table).toHaveTextContent('Ongoing');
    expect(table).toHaveTextContent('Essential · No growth');
  });

  it('does not offer expense creation to viewers', async () => {
    vi.stubGlobal(
      'fetch',
      standardFetch([], {
        ...editorAccess,
        can_edit: false,
        role: 'VIEWER',
      }),
    );
    await renderPage();

    expect(await screen.findByText(/view-only access/i)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Add expense' })).toBeNull();
  });

  it('creates a person-attributed dated expense', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    let cashflowRequests = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/access'))
          return Promise.resolve(response(editorAccess));
        if (path.endsWith('/lookups/household_expense_type'))
          return Promise.resolve(
            response([
              {
                category: 'household_expense_type',
                code: 'UTILITIES',
                display_name: 'Utilities',
                id: categoryId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith('/people'))
          return Promise.resolve(
            response([
              {
                display_name: 'Alex Household',
                effective_from: '2026-08-02',
                household_id: householdId,
                id: personId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith('/expenses') && init?.method === 'POST') {
          if (typeof init.body !== 'string') {
            throw new Error('Expected a JSON request body');
          }
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(response({ ...expense, ...requestBody }, 201));
        }
        if (path.endsWith('/expenses')) return Promise.resolve(response([]));
        if (path.includes('/cashflow?')) {
          cashflowRequests += 1;
          return Promise.resolve(response(emptyCashflow));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add expense' }),
    );
    await user.type(screen.getByLabelText('Expense name'), 'Electricity');
    await user.click(screen.getByLabelText('Category'));
    await user.click(await screen.findByText('Utilities'));
    await user.type(screen.getByLabelText('Amount (NZD)'), '210.75');
    await user.click(screen.getByLabelText('Paid for by (optional)'));
    await user.click(await screen.findByText('Alex Household'));
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add expense',
      }),
    );

    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody).toMatchObject({
      amount: '210.75',
      category_id: categoryId,
      display_name: 'Electricity',
      frequency: 'MONTHLY',
      is_essential: true,
      person_id: personId,
    });
    expect(await screen.findByText('Expense added')).toBeVisible();
    await waitFor(() => expect(cashflowRequests).toBe(2));
  }, 30_000);

  it('allows household-level creation when people cannot be loaded', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/access'))
          return Promise.resolve(response(editorAccess));
        if (path.endsWith('/lookups/household_expense_type'))
          return Promise.resolve(
            response([
              {
                category: 'household_expense_type',
                code: 'UTILITIES',
                display_name: 'Utilities',
                id: categoryId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith('/people'))
          return Promise.resolve(response({ detail: 'Unavailable' }, 500));
        if (path.endsWith('/expenses') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(response({ ...expense, ...requestBody }, 201));
        }
        if (path.endsWith('/expenses')) return Promise.resolve(response([]));
        if (path.includes('/cashflow?'))
          return Promise.resolve(response(emptyCashflow));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add expense' }),
    );
    expect(
      await screen.findByText(/will apply to the whole household/i),
    ).toBeVisible();
    await user.type(screen.getByLabelText('Expense name'), 'Water');
    await user.click(screen.getByLabelText('Category'));
    await user.click(await screen.findByText('Utilities'));
    await user.type(screen.getByLabelText('Amount (NZD)'), '80');
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Add expense',
      }),
    );
    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody?.person_id).toBeNull();
  }, 30_000);

  it('edits and removes an existing expense with confirmation', async () => {
    const user = userEvent.setup();
    let method: string | undefined;
    let cashflowRequests = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/access'))
          return Promise.resolve(response(editorAccess));
        if (path.endsWith('/lookups/household_expense_type'))
          return Promise.resolve(
            response([{ id: categoryId, display_name: 'Utilities' }]),
          );
        if (path.endsWith('/people')) return Promise.resolve(response([]));
        if (path.endsWith(`/expenses/${expense.id}`)) {
          method = init?.method;
          if (method === 'DELETE')
            return Promise.resolve(new Response(null, { status: 204 }));
          if (typeof init?.body !== 'string')
            throw new Error('Expected a JSON request body');
          return Promise.resolve(
            response({ ...expense, ...JSON.parse(init.body) }, 200),
          );
        }
        if (path.endsWith('/expenses'))
          return Promise.resolve(response([expense]));
        if (path.includes('/cashflow?')) {
          cashflowRequests += 1;
          return Promise.resolve(response(emptyCashflow));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    await renderPage();
    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.clear(screen.getByLabelText('Amount (NZD)'));
    await user.type(screen.getByLabelText('Amount (NZD)'), '130');
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', {
        name: 'Save changes',
      }),
    );
    expect(await screen.findByText('Expense updated')).toBeVisible();
    expect(method).toBe('PATCH');
    await waitFor(() => expect(cashflowRequests).toBe(2));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await user.click(await screen.findByRole('button', { name: 'Remove' }));
    await user.click(screen.getByRole('button', { name: 'Remove expense' }));
    expect(await screen.findByText('Expense removed')).toBeVisible();
    expect(method).toBe('DELETE');
    await waitFor(() => expect(cashflowRequests).toBe(3));
    expect(screen.queryByText('Groceries')).toBeNull();
  }, 30_000);

  it('clears and hides growth when frequency changes to one-off', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', standardFetch([]));
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add expense' }),
    );
    await user.click(screen.getByText('Advanced'));
    await user.type(
      screen.getByLabelText('Annual growth rate % (optional)'),
      '3',
    );
    await user.click(screen.getByLabelText('Frequency'));
    await user.click(screen.getByText('One-off'));
    expect(
      screen.queryByLabelText('Annual growth rate % (optional)'),
    ).toBeNull();
    expect(screen.getByText(/Growth does not apply/i)).toBeVisible();
  });
});

describe('expense validation', () => {
  const valid = {
    amount: '10.25',
    annualGrowthRate: '',
    categoryId,
    displayName: 'Council rates',
    effectiveFrom: '2026-08-02',
    effectiveTo: '',
    frequency: 'QUARTERLY' as const,
    isEssential: 'true' as const,
    notes: '',
    personId: '',
  };

  it('accepts recurring and one-off expenses', () => {
    expect(expenseSchema.safeParse(valid).success).toBe(true);
    expect(
      expenseSchema.safeParse({ ...valid, frequency: 'ONCE' }).success,
    ).toBe(true);
  });

  it('rejects growth for a one-off expense', () => {
    expect(
      expenseSchema.safeParse({
        ...valid,
        annualGrowthRate: '3',
        frequency: 'ONCE',
      }).success,
    ).toBe(false);
  });

  it.each([
    [{ ...valid, amount: '' }, 'amount'],
    [{ ...valid, amount: '-1' }, 'amount'],
    [{ ...valid, annualGrowthRate: '100.1' }, 'growth'],
    [{ ...valid, effectiveTo: '2026-08-01' }, 'date range'],
  ])('rejects an invalid %s', (fields) => {
    expect(expenseSchema.safeParse(fields).success).toBe(false);
  });
});
