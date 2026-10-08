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
const household = {
  currency: 'NZD',
  display_name: 'Example household',
  id: householdId,
  jurisdiction: 'NZ',
};
const account = {
  display_name: 'Plan Owner',
  email: null,
  global_role: 'USER',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'plan-owner',
};
const purchaseType = {
  category: 'purchase_type',
  code: 'ESTABLISHED_HOME',
  display_name: 'Established home',
  id: '00000000-0000-0000-0000-000000000002',
  is_active: true,
};
const provider = { code: 'AU', display_name: 'Australian purchase costs' };
const plan = {
  currency: 'NZD',
  desired_buffer: '10000.00',
  display_name: 'Next home',
  household_id: householdId,
  id: '00000000-0000-0000-0000-000000000003',
  intended_use: 'Owner occupied',
  max_lvr: '80',
  minimum_monthly_surplus: '500',
  notes: null,
  provider_code: 'AU',
  provider_settings: {},
  purchase_type_id: purchaseType.id,
  target_date: '2028-01-10',
  target_location: {},
  target_price_max: '900000.00',
  target_price_min: '750000.00',
};
const person = {
  display_name: 'Alex Example',
  effective_from: '2026-01-01',
  effective_to: null,
  household_id: householdId,
  id: '00000000-0000-0000-0000-000000000004',
  is_active: true,
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
  localStorage.setItem(selectionKeys.household, householdId);
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/purchase-plans'] }),
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

function standardFetch(canEdit = true, plans: unknown[] = []) {
  return vi.fn<typeof fetch>((input, init) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(response({ account }));
    if (path.endsWith('/households'))
      return Promise.resolve(response([household]));
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
    if (path.endsWith('/purchase-plans') && init?.method === 'POST')
      if (typeof init.body !== 'string') throw new Error('Expected JSON body');
    if (path.endsWith('/purchase-plans') && init?.method === 'POST')
      return Promise.resolve(
        response(
          {
            ...JSON.parse(init.body as string),
            household_id: householdId,
            id: '00000000-0000-0000-0000-000000000003',
          },
          201,
        ),
      );
    if (path.endsWith('/purchase-plans'))
      return Promise.resolve(response(plans));
    if (path.endsWith('/lookups/purchase_type'))
      return Promise.resolve(response([purchaseType]));
    if (path.endsWith('/purchase-providers'))
      return Promise.resolve(response([provider]));
    if (path.endsWith(`/purchase-plans/${plan.id}`))
      return Promise.resolve(
        response({
          ...plan,
          costs: [
            {
              amount: '1200.00',
              code: 'INSPECTION',
              display_name: 'Building inspection',
              id: '00000000-0000-0000-0000-000000000006',
              is_estimate: true,
              purchase_plan_id: plan.id,
              revision: 1,
            },
          ],
          funding_sources: [
            {
              amount: '150000.00',
              available_date: '2027-12-01',
              display_name: 'Savings',
              id: '00000000-0000-0000-0000-000000000005',
              is_borrowed: false,
              notes: null,
              purchase_plan_id: plan.id,
              revision: 1,
              source_type: 'CASH',
            },
          ],
          ownership: [
            {
              external_owner_name: null,
              id: '00000000-0000-0000-0000-000000000007',
              owner_type: 'PERSON',
              ownership_percentage: '100',
              person_id: person.id,
              purchase_plan_id: plan.id,
              revision: 1,
            },
          ],
        }),
      );
    if (path.includes(`/purchase-plans/${plan.id}/`))
      return Promise.resolve(response({}, init?.method === 'POST' ? 201 : 200));
    if (path.endsWith('/people')) return Promise.resolve(response([person]));
    throw new Error(`Unexpected request: ${path}`);
  });
}

describe('purchase plan records', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('shows saved plans with friendly type and provider names', async () => {
    vi.stubGlobal('fetch', standardFetch(true, [plan]));
    await renderPage();

    expect(await screen.findByText('Next home')).toBeVisible();
    expect(screen.getByText('Established home')).toBeVisible();
    expect(screen.getByText('Australian purchase costs')).toBeVisible();
  });

  it('opens complete plan details with friendly ownership labels', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', standardFetch(true, [plan]));
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'View details' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Next home' });

    expect(within(dialog).getByText('Savings')).toBeVisible();
    expect(within(dialog).getByText('Building inspection')).toBeVisible();
    expect(within(dialog).getByText('Alex Example')).toBeVisible();
    expect(within(dialog).getByText('NZ$150,000.00')).toBeVisible();
  });

  it('sends precise funding and ownership mutations from the detail view', async () => {
    const user = userEvent.setup();
    const fetchMock = standardFetch(true, [plan]);
    vi.stubGlobal('fetch', fetchMock);
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'View details' }),
    );
    const detail = await screen.findByRole('dialog', { name: 'Next home' });
    await user.click(
      within(detail).getByRole('button', { name: 'Add funding source' }),
    );
    const editor = await screen.findByRole('dialog', {
      name: 'Add funding source',
    });
    await user.type(within(editor).getByLabelText('Name'), 'Gift');
    await user.type(within(editor).getByLabelText('Source type'), 'GIFT');
    await user.type(
      within(editor).getByLabelText('Available date'),
      '2027-01-15',
    );
    await user.type(within(editor).getByLabelText('Amount'), '25000.25');
    await user.click(within(editor).getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith('/funding-sources') &&
            init?.method === 'POST' &&
            typeof init.body === 'string' &&
            init.body.includes('25000.25'),
        ),
      ).toBe(true),
    );

    await user.click(
      within(detail).getByRole('button', { name: 'Replace ownership' }),
    );
    const ownership = await screen.findByRole('dialog', {
      name: 'Replace proposed ownership',
    });
    await user.click(
      within(ownership).getByRole('button', { name: 'Replace ownership' }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith('/ownership') && init?.method === 'PUT',
        ),
      ).toBe(true),
    );
  });

  it('keeps detail records read-only for viewers', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', standardFetch(false, [plan]));
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'View details' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Next home' });

    expect(within(dialog).getByText('Savings')).toBeVisible();
    expect(
      within(dialog).queryByRole('button', { name: 'Add funding source' }),
    ).toBeNull();
    expect(
      within(dialog).queryByRole('button', { name: 'Replace ownership' }),
    ).toBeNull();
  });

  it('requires confirmation before removing a saved financial input', async () => {
    const user = userEvent.setup();
    const fetchMock = standardFetch(true, [plan]);
    vi.stubGlobal('fetch', fetchMock);
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'View details' }),
    );
    const detail = await screen.findByRole('dialog', { name: 'Next home' });
    const costRow = within(detail)
      .getByText('Building inspection')
      .closest('tr');
    if (!costRow) throw new Error('Expected cost row');
    await user.click(within(costRow).getByRole('button', { name: 'Remove' }));

    const confirmation = await screen.findByRole('dialog', {
      name: 'Remove Building inspection?',
    });
    expect(within(confirmation).getByText(/audited history/i)).toBeVisible();
    await user.click(
      within(confirmation).getByRole('button', { name: 'Remove' }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith(
              '/costs/00000000-0000-0000-0000-000000000006',
            ) && init?.method === 'DELETE',
        ),
      ).toBe(true),
    );
  });

  it('distinguishes a failed detail request and offers retry', async () => {
    const user = userEvent.setup();
    const fallback = standardFetch(true, [plan]);
    let detailAttempts = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        if (pathOf(input).endsWith(`/purchase-plans/${plan.id}`)) {
          detailAttempts += 1;
          return Promise.resolve(
            response({ detail: 'Temporary failure' }, 500),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'View details' }),
    );
    const dialog = await screen.findByRole('dialog', {
      name: 'Purchase plan details',
    });

    expect(within(dialog).getByText(/Temporary failure/)).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(detailAttempts).toBe(2));
  });

  it('does not offer creation to a viewer', async () => {
    vi.stubGlobal('fetch', standardFetch(false));
    await renderPage();

    expect(await screen.findByText(/view-only access/i)).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Add purchase plan' }),
    ).toBeNull();
  });

  it('creates a country-neutral plan with an installed provider', async () => {
    const user = userEvent.setup();
    const fetchMock = standardFetch();
    vi.stubGlobal('fetch', fetchMock);
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add purchase plan' }),
    );
    const dialog = await screen.findByRole('dialog', {
      name: 'Add purchase plan',
    });
    await user.type(
      within(dialog).getByRole('textbox', { name: /Plan name/ }),
      'First investment',
    );
    await user.click(
      within(dialog).getByRole('combobox', { name: /Purchase type/ }),
    );
    await user.click(screen.getByRole('option', { name: 'Established home' }));
    await user.type(
      within(dialog).getByLabelText('Minimum price (NZD)'),
      '500000',
    );
    await user.type(
      within(dialog).getByLabelText('Maximum price (NZD)'),
      '650000',
    );
    await user.click(within(dialog).getByText('Advanced'));
    await user.click(within(dialog).getByLabelText('Purchase cost provider'));
    await user.click(
      screen.getByRole('option', { name: provider.display_name }),
    );
    await user.click(within(dialog).getByRole('button', { name: 'Save plan' }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([input, init]) =>
          pathOf(input).endsWith('/purchase-plans') && init?.method === 'POST',
      );
      expect(call).toBeDefined();
      const body = call?.[1]?.body;
      if (typeof body !== 'string') throw new Error('Expected JSON body');
      expect(JSON.parse(body)).toMatchObject({
        costs: [],
        currency: 'NZD',
        display_name: 'First investment',
        funding_sources: [],
        ownership: [],
        provider_code: 'AU',
        target_price_max: '650000',
        target_price_min: '500000',
      });
    });
  });

  it('rejects unsafe monetary formats before sending them', async () => {
    const user = userEvent.setup();
    const fetchMock = standardFetch();
    vi.stubGlobal('fetch', fetchMock);
    await renderPage();
    await user.click(
      await screen.findByRole('button', { name: 'Add purchase plan' }),
    );
    const dialog = await screen.findByRole('dialog', {
      name: 'Add purchase plan',
    });
    await user.type(
      within(dialog).getByRole('textbox', { name: /Plan name/ }),
      'Unsafe plan',
    );
    await user.click(
      within(dialog).getByRole('combobox', { name: /Purchase type/ }),
    );
    await user.click(screen.getByRole('option', { name: 'Established home' }));
    await user.type(
      within(dialog).getByLabelText('Minimum price (NZD)'),
      '1e5',
    );
    await user.type(
      within(dialog).getByLabelText('Maximum price (NZD)'),
      '100.001',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Save plan' }));

    expect(
      await within(dialog).findByText(/no more than two decimal places/i),
    ).toBeVisible();
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          pathOf(input).endsWith('/purchase-plans') && init?.method === 'POST',
      ),
    ).toBe(false);
  });
});
