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

const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const propertyId = '818badb5-2518-4c3f-8f6d-bb6ee750e606';
const typeId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';
const statusId = '85e30193-a324-4d22-9065-e25d819f6530';
const account = {
  display_name: 'Property Owner',
  email: null,
  global_role: 'USER',
  id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
  must_change_password: false,
  username: 'property-owner',
};
const household = {
  currency: 'NZD',
  display_name: 'Property household',
  id: householdId,
  jurisdiction: 'NZ',
};
const summary = {
  currency: 'NZD',
  current_status_id: statusId,
  current_value: '780000.00',
  display_name: 'Harbour home',
  id: propertyId,
  position_date: '2026-06-30',
  property_type_id: typeId,
  purchase_date: '2020-02-01',
  purchase_price: '520000.00',
  setup_mode: 'CURRENT_SNAPSHOT',
  total_property_debt: '310000.00',
};
const detail = {
  address_line_1: '4 Example Street',
  address_line_2: null,
  country_code: 'NZ',
  current_status_id: statusId,
  default_currency: 'NZD',
  display_name: 'Harbour home',
  household_id: householdId,
  id: propertyId,
  notes: 'Our main home',
  postal_code: '6011',
  property_type_id: typeId,
  purchase_date: '2020-02-01',
  purchase_price: '520000.00',
  sale_date: null,
  state_or_region: 'Wellington',
  suburb_or_locality: 'Island Bay',
};
const resolvedState = {
  applied_event_ids: [],
  as_of: '2026-08-02',
  baseline_date: '2026-06-30',
  baseline_id: '7023926d-f832-4190-94b6-6464df29dac2',
  data_quality_flags: [],
  is_active_asset: true,
  loan_balance_total: '305000.00',
  property_id: propertyId,
  property_value: '790000.00',
  status_id: statusId,
  temporal_position: 'CURRENT',
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

function standardFetch(summaries: unknown = [summary]) {
  return vi.fn<typeof fetch>((input) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(response({ account }));
    if (path.endsWith('/households'))
      return Promise.resolve(response([household]));
    if (path.endsWith('/property-summaries'))
      return Promise.resolve(response(summaries));
    if (path.endsWith('/lookups/property_type'))
      return Promise.resolve(
        response([
          { id: typeId, code: 'HOUSE', display_name: 'House', is_active: true },
        ]),
      );
    if (path.endsWith('/lookups/property_status'))
      return Promise.resolve(
        response([
          { id: statusId, code: 'HOME', display_name: 'Home', is_active: true },
        ]),
      );
    if (path.endsWith(`/properties/${propertyId}`))
      return Promise.resolve(response(detail));
    if (path.includes(`/properties/${propertyId}/state?`))
      return Promise.resolve(response(resolvedState));
    throw new Error(`Unexpected request: ${path}`);
  });
}

async function renderPage() {
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/properties'] }),
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

describe('property overview workflows', () => {
  beforeEach(() => localStorage.setItem(selectionKeys.household, householdId));

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('keeps purchase price, current value and total debt distinct', async () => {
    vi.stubGlobal('fetch', standardFetch());
    await renderPage();

    const table = await screen.findByRole('table', {
      name: 'Household properties',
    });
    expect(table).toHaveTextContent('Harbour home');
    expect(table).toHaveTextContent('House');
    expect(table).toHaveTextContent('Home');
    expect(table).toHaveTextContent('NZ$520,000.00');
    expect(table).toHaveTextContent('NZ$780,000.00');
    expect(table).toHaveTextContent('NZ$310,000.00');
    expect(screen.getByText(/choose a property/i)).toBeVisible();
  });

  it('selects and restores a property with its resolved position', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', standardFetch());
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    expect(localStorage.getItem(selectionKeys.property)).toBe(propertyId);
    expect(
      await screen.findByText(
        '4 Example Street, Island Bay, Wellington, 6011, NZ',
      ),
    ).toBeVisible();
    expect(screen.getByText('Our main home')).toBeVisible();
    expect(await screen.findByText(/Results as of 2026-08-02/)).toBeVisible();
    expect(screen.getByText('NZ$790,000.00')).toBeVisible();
    expect(screen.getByText('NZ$305,000.00')).toBeVisible();
    expect(screen.getByText(/Status: Home · Active asset: Yes/)).toBeVisible();
  });

  it('keeps the result date explicit until a changed date is refreshed', async () => {
    const user = userEvent.setup();
    localStorage.setItem(selectionKeys.property, propertyId);
    vi.stubGlobal('fetch', standardFetch());
    await renderPage();
    await screen.findByText(/Results as of 2026-08-02/);

    const date = screen.getByLabelText('Position date');
    await user.clear(date);
    await user.type(date, '2028-07-01');

    expect(screen.getByText(/position date has changed/i)).toBeVisible();
    expect(screen.getByText(/Results as of 2026-08-02/)).toBeVisible();
  });

  it('clears a property selection that is not in the selected household', async () => {
    localStorage.setItem(selectionKeys.property, propertyId);
    vi.stubGlobal('fetch', standardFetch([]));
    await renderPage();

    expect(await screen.findByText('No properties recorded')).toBeVisible();
    await waitFor(() =>
      expect(localStorage.getItem(selectionKeys.property)).toBeNull(),
    );
  });

  it('reports property-list failures instead of an empty household', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith('/property-summaries'))
          return Promise.resolve(response({ detail: 'Unavailable' }, 500));
        if (path.includes('/lookups/')) return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    await renderPage();

    expect(
      await screen.findByText(/Properties could not be loaded/),
    ).toBeVisible();
    expect(screen.queryByText('No properties recorded')).toBeNull();
  });
});
