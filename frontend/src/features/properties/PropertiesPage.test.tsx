import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  RouterProvider,
  createMemoryHistory,
  type AnyRouter,
} from '@tanstack/react-router';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
const expenseTypeId = '487288b5-9cf2-4760-b903-dce0e5c09627';
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
  applied_event_ids: ['f24b092f-ef89-480d-8eab-f2c93e68f53a'],
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
  valuation_date: null,
  valuation_id: null,
  valuation_is_estimate: null,
  valuation_type: null,
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

function standardFetch(
  summaries: unknown = [summary],
  rentalProfiles: unknown = [],
) {
  return vi.fn<typeof fetch>((input) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(response({ account }));
    if (path.endsWith('/households'))
      return Promise.resolve(response([household]));
    if (path.endsWith(`/households/${householdId}/access`))
      return Promise.resolve(
        response({ can_edit: true, can_manage: true, role: 'OWNER' }),
      );
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
    if (path.endsWith(`/households/${householdId}/people`))
      return Promise.resolve(
        response([
          {
            display_name: 'Alex',
            effective_from: '2020-01-01',
            id: '8a76ff72-b719-4ca9-9f77-b66f901fb56f',
            is_active: true,
          },
        ]),
      );
    if (path.endsWith(`/properties/${propertyId}/ownership`))
      return Promise.resolve(response([]));
    if (path.includes(`/properties/${propertyId}/ownership-position?`))
      return Promise.resolve(
        response({
          as_of: '2026-08-17',
          ownership: [],
          total_percentage: '0.00',
          warnings: [
            'Ownership totals 0.00% rather than 100.00% for the effective date',
          ],
        }),
      );
    if (path.endsWith(`/properties/${propertyId}/rental-profiles`))
      return Promise.resolve(response(rentalProfiles));
    if (path.endsWith('/lookups/property_expense_type'))
      return Promise.resolve(
        response([
          {
            id: expenseTypeId,
            code: 'INSURANCE',
            display_name: 'Insurance',
            is_active: true,
          },
        ]),
      );
    if (path.endsWith(`/properties/${propertyId}/expenses`))
      return Promise.resolve(response([]));
    if (path.includes(`/properties/${propertyId}/cashflow?`))
      return Promise.resolve(
        response({
          charged_rent_equivalent: '18200.00',
          currency: 'NZD',
          from_date: '2026-01-01',
          gross_rent: '18200.00',
          letting_fees: '0.00',
          management_fee: '1324.05',
          market_rent_equivalent: '20800.00',
          net_cashflow: '15129.95',
          property_expenses: '1200.00',
          property_id: propertyId,
          rent_difference: '-2600.00',
          rental_days: 365,
          to_date: '2026-12-31',
          vacancy_cost: '546.00',
          warnings: ['Recurring amounts use a 365-day planning year'],
        }),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
}

async function renderPage() {
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/properties'] }),
  });
  const view = render(
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
  return view;
}

describe('property overview workflows', () => {
  beforeEach(() => localStorage.setItem(selectionKeys.household, householdId));

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('labels baseline amounts with their recorded date', async () => {
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
    expect(table).toHaveTextContent('Recorded value');
    expect(table).toHaveTextContent('Recorded debt');
    expect(table).toHaveTextContent('Recorded at');
    expect(table).toHaveTextContent('Jun 30, 2026');
    expect(screen.getByText(/choose a property/i)).toBeVisible();
  });

  it('shows an event-adjusted position separately from its older baseline', async () => {
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
    expect(screen.getByText('Recorded Jun 30, 2026')).toBeVisible();
    expect(screen.getByText('From the latest complete position')).toBeVisible();
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
        if (path.endsWith(`/households/${householdId}/access`))
          return Promise.resolve(
            response({ can_edit: true, can_manage: true, role: 'OWNER' }),
          );
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

  it('reports reference-data failures and retries them', async () => {
    const user = userEvent.setup();
    let typeAttempts = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/auth/session'))
          return Promise.resolve(response({ account }));
        if (path.endsWith('/households'))
          return Promise.resolve(response([household]));
        if (path.endsWith(`/households/${householdId}/access`))
          return Promise.resolve(
            response({ can_edit: true, can_manage: true, role: 'OWNER' }),
          );
        if (path.endsWith('/property-summaries'))
          return Promise.resolve(response([summary]));
        if (path.endsWith('/lookups/property_type')) {
          typeAttempts += 1;
          return Promise.resolve(
            typeAttempts === 1
              ? response({ detail: 'Catalogue unavailable' }, 503)
              : response([
                  {
                    id: typeId,
                    code: 'HOUSE',
                    display_name: 'House',
                    is_active: true,
                  },
                ]),
          );
        }
        if (path.endsWith('/lookups/property_status')) {
          return Promise.resolve(
            response([
              {
                id: statusId,
                code: 'HOME',
                display_name: 'Home',
                is_active: true,
              },
            ]),
          );
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    await renderPage();

    expect(
      await screen.findByText(/Property types could not be loaded/),
    ).toBeVisible();
    expect(screen.getByRole('table')).toHaveTextContent(
      'Reference data unavailable',
    );
    await user.click(
      screen.getByRole('button', { name: 'Retry property types' }),
    );
    await waitFor(() =>
      expect(
        screen.queryByText(/Property types could not be loaded/),
      ).toBeNull(),
    );
    expect(screen.getByRole('table')).toHaveTextContent('House');
  });

  it('creates a current position with only its dated baseline fields', async () => {
    const user = userEvent.setup();
    const createdPropertyId = 'd5dab911-5253-4cb1-b854-183faba41f4b';
    let saved: Record<string, unknown> | null = null;
    let created = false;
    let refetchReleased = false;
    let resolveRefetch!: (response: Response) => void;
    const delayedSummary = new Promise<Response>((resolve) => {
      resolveRefetch = resolve;
    });
    const fallback = standardFetch([]);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/property-summaries')) {
          if (!created) return Promise.resolve(response([]));
          return refetchReleased
            ? Promise.resolve(
                response([
                  {
                    ...summary,
                    display_name: 'New current home',
                    id: createdPropertyId,
                  },
                ]),
              )
            : delayedSummary;
        }
        if (path.endsWith('/reference/countries')) {
          return Promise.resolve(response([]));
        }
        if (path.endsWith('/properties/wizard') && init?.method === 'POST') {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          created = true;
          return Promise.resolve(
            response(
              {
                baseline: {
                  baseline_date: '2026-08-02',
                  id: '7023926d-f832-4190-94b6-6464df29dac2',
                  loan_balance_total: '310000.00',
                  notes: null,
                  property_id: createdPropertyId,
                  property_value: '780000.00',
                  status_id: statusId,
                },
                ownership: [],
                property: {
                  ...detail,
                  display_name: 'New current home',
                  id: createdPropertyId,
                },
                valuation: null,
                warnings: [],
              },
              201,
            ),
          );
        }
        if (path.endsWith(`/properties/${createdPropertyId}`)) {
          return Promise.resolve(
            response({ ...detail, id: createdPropertyId }),
          );
        }
        if (path.includes(`/properties/${createdPropertyId}/state?`)) {
          return Promise.resolve(
            response({ ...resolvedState, property_id: createdPropertyId }),
          );
        }
        return fallback(input, init);
      }),
    );
    const view = await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Add property' }),
    );
    await user.type(screen.getByLabelText('Property name'), 'Harbour home');
    await user.click(screen.getByLabelText('Property type'));
    await user.click(screen.getByRole('option', { name: 'House' }));
    await user.click(screen.getByLabelText('Current use'));
    await user.click(screen.getByRole('option', { name: 'Home' }));
    await user.type(screen.getByLabelText('Property value (NZD)'), '780000');
    await user.type(
      screen.getByLabelText('Total property debt (NZD)'),
      '310000',
    );
    await user.click(screen.getByRole('button', { name: 'Save property' }));

    expect(await screen.findByText('Property added')).toBeVisible();
    expect(localStorage.getItem(selectionKeys.property)).toBe(
      createdPropertyId,
    );
    expect(
      await screen.findByRole('button', { name: 'Selected' }),
    ).toBeVisible();
    expect(saved).toMatchObject({
      baseline: {
        loan_balance_total: '310000',
        property_value: '780000',
        status_id: statusId,
      },
      mode: 'CURRENT_SNAPSHOT',
      property: {
        display_name: 'Harbour home',
        purchase_date: null,
        purchase_price: null,
      },
    });
    refetchReleased = true;
    resolveRefetch(
      response([
        {
          ...summary,
          display_name: 'New current home',
          id: createdPropertyId,
        },
      ]),
    );
    await waitFor(() =>
      expect(screen.getByRole('table')).toHaveTextContent('New current home'),
    );
    view.unmount();
    await renderPage();
    expect(
      await screen.findByRole('button', { name: 'Selected' }),
    ).toBeVisible();
    expect(localStorage.getItem(selectionKeys.property)).toBe(
      createdPropertyId,
    );
  });

  it('creates purchase history without implying current value or debt', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    const fallback = standardFetch([]);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/reference/countries')) {
          return Promise.resolve(
            response({ detail: 'Country catalogue unavailable' }, 503),
          );
        }
        if (path.endsWith('/properties/wizard') && init?.method === 'POST') {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          return Promise.resolve(
            response(
              {
                baseline: null,
                ownership: [],
                property: detail,
                valuation: {
                  id: '95a93508-f1fc-421f-a56d-16e6fd9e557d',
                },
                warnings: [],
              },
              201,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Add property' }),
    );
    await user.click(screen.getByLabelText('How would you like to start?'));
    await user.click(
      screen.getByRole('option', { name: 'Historical purchase' }),
    );
    expect(
      screen.getByText(/does not mean the property is debt-free/i),
    ).toBeVisible();
    expect(
      await screen.findByText(/household country remains selected/i),
    ).toBeVisible();
    await user.click(screen.getByText(/Add the property address/i));
    expect(screen.getByLabelText('Country (optional)')).toHaveValue(
      '🌐 NZ (household country)',
    );
    await user.type(screen.getByLabelText('Property name'), 'Earlier purchase');
    await user.click(screen.getByLabelText('Property type'));
    await user.click(screen.getByRole('option', { name: 'House' }));
    await user.click(screen.getByLabelText('Current use'));
    await user.click(screen.getByRole('option', { name: 'Home' }));
    await user.type(screen.getByLabelText('Purchase date'), '2020-02-01');
    await user.type(screen.getByLabelText('Purchase price (NZD)'), '520000');
    await user.click(screen.getByRole('button', { name: 'Save property' }));

    expect(await screen.findByText('Property added')).toBeVisible();
    expect(saved).toMatchObject({
      baseline: null,
      mode: 'HISTORICAL_PURCHASE',
      property: {
        country_code: 'NZ',
        display_name: 'Earlier purchase',
        purchase_date: '2020-02-01',
        purchase_price: '520000',
      },
    });
    expect(saved).not.toHaveProperty('property.current_value');
    expect(saved).not.toHaveProperty('property.total_property_debt');
  });

  it('adds a current position to an existing property record', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    let updated = false;
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/reference/countries')) {
          return Promise.resolve(response([]));
        }
        if (path.endsWith('/property-summaries') && updated) {
          return Promise.resolve(
            response([
              {
                ...summary,
                current_value: '825000.00',
                position_date: '2026-09-01',
                total_property_debt: '295000.00',
              },
            ]),
          );
        }
        if (
          path.endsWith(`/properties/${propertyId}/baselines`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          updated = true;
          return Promise.resolve(
            response(
              {
                baseline_date: '2026-09-01',
                id: 'd054419c-1ff9-48ec-a8ea-d5d5468d05c5',
                loan_balance_total: '295000.00',
                notes: null,
                property_id: propertyId,
                property_value: '825000.00',
                status_id: statusId,
              },
              201,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Add property' }),
    );
    await user.click(screen.getByLabelText('Property to update'));
    await user.click(screen.getByRole('option', { name: 'Harbour home' }));
    expect(screen.queryByLabelText('Property name')).toBeNull();
    expect(screen.queryByLabelText('Property type')).toBeNull();
    await user.click(screen.getByLabelText('Current use'));
    await user.click(screen.getByRole('option', { name: 'Home' }));
    await user.clear(screen.getByLabelText('Position date'));
    await user.type(screen.getByLabelText('Position date'), '2026-09-01');
    await user.type(screen.getByLabelText('Property value (NZD)'), '825000');
    await user.type(
      screen.getByLabelText('Total property debt (NZD)'),
      '295000',
    );
    await user.click(
      screen.getByRole('button', { name: 'Save current position' }),
    );

    expect(await screen.findByText('Current position recorded')).toBeVisible();
    expect(saved).toEqual({
      baseline_date: '2026-09-01',
      loan_balance_total: '295000',
      property_value: '825000',
      status_id: statusId,
    });
    const table = await screen.findByRole('table');
    expect(table).toHaveTextContent('NZ$825,000.00');
    expect(table).toHaveTextContent('NZ$295,000.00');
    expect(localStorage.getItem(selectionKeys.property)).toBe(propertyId);
  });

  it('records a valuation and refreshes its dated resolved value', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    let valuationAdded = false;
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/properties/${propertyId}/valuations`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          valuationAdded = true;
          return Promise.resolve(
            response(
              {
                id: '00d8bb19-b984-47f6-95e4-f804585803ff',
                is_estimate: false,
                notes: null,
                property_id: propertyId,
                source: 'Independent valuer',
                valuation_date: '2026-07-15',
                valuation_type: 'FORMAL_VALUATION',
                value: '805000.00',
              },
              201,
            ),
          );
        }
        if (
          valuationAdded &&
          path.includes(`/properties/${propertyId}/state?`)
        ) {
          return Promise.resolve(
            response({
              ...resolvedState,
              property_value: '805000.00',
              valuation_date: '2026-07-15',
              valuation_id: '00d8bb19-b984-47f6-95e4-f804585803ff',
              valuation_is_estimate: false,
              valuation_type: 'FORMAL_VALUATION',
            }),
          );
        }
        if (valuationAdded && path.endsWith('/property-summaries')) {
          return Promise.resolve(
            response([
              {
                ...summary,
                current_value: '805000.00',
                position_date: '2026-07-15',
              },
            ]),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(screen.getByRole('button', { name: 'Add dated record' }));
    await user.clear(screen.getByLabelText('Record date'));
    await user.type(screen.getByLabelText('Record date'), '2026-07-15');
    await user.type(screen.getByLabelText('Property value (NZD)'), '805000');
    await user.click(screen.getByLabelText('Valuation type'));
    await user.click(screen.getByRole('option', { name: 'Formal valuation' }));
    expect(
      screen.getByText('A formal valuation is recorded as a non-estimate.'),
    ).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Advanced' }));
    await user.type(
      screen.getByLabelText('Source (optional)'),
      'Independent valuer',
    );
    await user.click(screen.getByRole('button', { name: 'Save record' }));

    expect(await screen.findByText('Valuation recorded')).toBeVisible();
    expect(saved).toEqual({
      is_estimate: false,
      notes: null,
      source: 'Independent valuer',
      valuation_date: '2026-07-15',
      valuation_type: 'FORMAL_VALUATION',
      value: '805000',
    });
    expect(
      await screen.findByText('Valuation recorded Jul 15, 2026'),
    ).toBeVisible();
    expect(screen.getAllByText('NZ$805,000.00')).toHaveLength(3);
  });

  it('records a complete baseline with explicit debt and status', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/properties/${propertyId}/baselines`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          return Promise.resolve(
            response(
              {
                accumulated_cost_base: '560000.00',
                baseline_date: '2026-07-31',
                id: 'ba558658-2fe9-49a4-8d55-30dfde31c867',
                loan_balance_total: '300000.00',
                notes: 'End of month records',
                property_id: propertyId,
                property_value: '810000.00',
                status_id: statusId,
              },
              201,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(screen.getByRole('button', { name: 'Add dated record' }));
    await user.click(screen.getByLabelText('Record type'));
    await user.click(
      screen.getByRole('option', { name: 'Complete position baseline' }),
    );
    await user.clear(screen.getByLabelText('Record date'));
    await user.type(screen.getByLabelText('Record date'), '2026-07-31');
    await user.type(screen.getByLabelText('Property value (NZD)'), '810000');
    await user.type(
      screen.getByLabelText('Total property debt (NZD)'),
      '300000',
    );
    await user.click(screen.getByLabelText('Property use'));
    await user.click(screen.getByRole('option', { name: 'Home' }));
    await user.click(screen.getByRole('button', { name: 'Advanced' }));
    await user.type(
      screen.getByLabelText('Accumulated cost base (NZD, optional)'),
      '560000',
    );
    await user.type(
      screen.getByLabelText('Notes (optional)'),
      'End of month records',
    );
    await user.click(screen.getByRole('button', { name: 'Save record' }));

    expect(await screen.findByText('Baseline recorded')).toBeVisible();
    expect(saved).toEqual({
      accumulated_cost_base: '560000',
      baseline_date: '2026-07-31',
      loan_balance_total: '300000',
      notes: 'End of month records',
      property_value: '810000',
      status_id: statusId,
    });
  });

  it('adds dated ownership for a household person and reports an incomplete total', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/properties/${propertyId}/ownership`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          return Promise.resolve(
            response(
              {
                ownership: {
                  ...saved,
                  id: 'f263fb67-ff9f-4469-8d81-b89f07146624',
                  property_id: propertyId,
                },
                total_percentage: '60.00',
                warnings: [
                  'Ownership totals 60.00% rather than 100.00% for the effective date',
                ],
              },
              201,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(screen.getByRole('button', { name: 'Refresh ownership' }));
    await user.click(
      screen.getByRole('button', { name: 'Add ownership record' }),
    );
    await user.click(screen.getByLabelText('Owner'));
    await user.click(
      screen.getByRole('option', { name: 'A person in this household' }),
    );
    await user.click(screen.getByLabelText('Person'));
    await user.click(screen.getByRole('option', { name: 'Alex' }));
    await user.type(screen.getByLabelText('Ownership percentage'), '60');
    await user.clear(screen.getByLabelText('Effective from'));
    await user.type(screen.getByLabelText('Effective from'), '2020-02-01');
    await user.click(screen.getByRole('button', { name: 'Save ownership' }));

    expect(
      await screen.findByText(/Ownership saved\. Ownership totals 60\.00%/),
    ).toBeVisible();
    expect(saved).toEqual({
      effective_from: '2020-02-01',
      effective_to: null,
      external_owner_name: null,
      notes: null,
      owner_type: 'PERSON',
      ownership_percentage: '60',
      person_id: '8a76ff72-b719-4ca9-9f77-b66f901fb56f',
    });
  });

  it('explains owner choices and reports a duplicate owner conflict', async () => {
    const user = userEvent.setup();
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/properties/${propertyId}/ownership`) &&
          init?.method === 'POST'
        ) {
          return Promise.resolve(
            response(
              {
                detail:
                  'This owner already has an ownership record for the selected dates. Correct or close the existing record before adding another.',
              },
              409,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(
      screen.getByRole('button', { name: 'Add ownership record' }),
    );
    expect(
      screen.getByText('Household jointly', { selector: 'strong' }),
    ).toBeVisible();
    expect(screen.getByText(/records one combined share/)).toBeVisible();
    await user.click(screen.getByLabelText('Owner'));
    await user.click(screen.getByRole('option', { name: 'Someone else' }));
    expect(screen.getByLabelText('Owner name')).toBeVisible();
    await user.click(screen.getByLabelText('Owner'));
    await user.click(screen.getByRole('option', { name: 'Household jointly' }));
    await user.type(screen.getByLabelText('Ownership percentage'), '60');
    await user.click(screen.getByRole('button', { name: 'Save ownership' }));

    expect(
      await screen.findByText(/Correct or close the existing record/),
    ).toBeVisible();
  });

  it('closes an ongoing ownership record before a transfer', async () => {
    const user = userEvent.setup();
    let corrected: Record<string, unknown> | null = null;
    const ownershipId = '018e6f8b-7bd7-40dc-aad0-bb694421fbbd';
    const record = {
      effective_from: '2020-01-01',
      effective_to: null,
      external_owner_name: null,
      id: ownershipId,
      notes: null,
      owner_type: 'HOUSEHOLD',
      ownership_percentage: '100.00',
      person_id: null,
      property_id: propertyId,
    };
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/properties/${propertyId}/ownership/${ownershipId}`) &&
          init?.method === 'PATCH'
        ) {
          corrected = JSON.parse(init.body as string) as Record<
            string,
            unknown
          >;
          return Promise.resolve(
            response({
              ownership: { ...record, ...corrected },
              total_percentage: '100.00',
              warnings: [],
            }),
          );
        }
        if (path.endsWith(`/properties/${propertyId}/ownership`)) {
          return Promise.resolve(response([record]));
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(
      await screen.findByRole('button', { name: 'Correct or end' }),
    );
    expect(screen.getByText(/end this record the day before/)).toBeVisible();
    await user.type(screen.getByLabelText('Effective to'), '2026-06-30');
    await user.type(
      screen.getByLabelText('Correction notes (optional)'),
      'Transferred',
    );
    await user.click(screen.getByRole('button', { name: 'Save correction' }));

    expect(await screen.findByText('Ownership record corrected')).toBeVisible();
    expect(corrected).toEqual({
      effective_to: '2026-06-30',
      notes: 'Transferred',
      ownership_percentage: '100.00',
    });
  });

  it('adds a partial rental arrangement with explicit household assumptions', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/properties/${propertyId}/rental-profiles`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          return Promise.resolve(
            response(
              {
                ...saved,
                id: 'a57994c3-76a7-475f-ae76-bf17228f04b4',
                property_id: propertyId,
              },
              201,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(
      screen.getByRole('button', { name: 'Add rental arrangement' }),
    );
    await user.click(screen.getByLabelText('Rental scope'));
    await user.click(
      screen.getByRole('option', { name: 'Part of the property' }),
    );
    fireEvent.change(screen.getByLabelText('Rental area name'), {
      target: { value: 'Granny flat' },
    });
    fireEvent.change(screen.getByLabelText('Property share (%)'), {
      target: { value: '30' },
    });
    fireEvent.change(
      screen.getByLabelText('Rent charged for this arrangement (NZD)'),
      {
        target: { value: '350' },
      },
    );
    fireEvent.change(
      screen.getByLabelText(
        'Comparable market rent for this arrangement (NZD, optional)',
      ),
      { target: { value: '400' } },
    );
    fireEvent.change(screen.getByLabelText('Vacancy allowance (%)'), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByLabelText('Management fee (%)'), {
      target: { value: '7.5' },
    });
    fireEvent.change(screen.getByLabelText('Letting fee (NZD, optional)'), {
      target: { value: '200' },
    });
    fireEvent.change(screen.getByLabelText('Effective from'), {
      target: { value: '2026-09-01' },
    });
    await user.click(
      screen.getByRole('button', { name: 'Save rental arrangement' }),
    );

    expect(await screen.findByText('Rental arrangement saved')).toBeVisible();
    expect(saved).toEqual({
      charged_rent_amount: '350',
      display_name: 'Granny flat',
      effective_from: '2026-09-01',
      effective_to: null,
      frequency: 'WEEKLY',
      letting_fee: '200',
      management_fee_rate: '7.5',
      market_rent_amount: '400',
      notes: null,
      rental_share_percentage: '30',
      vacancy_rate: '3',
    });
  }, 30_000);

  it('corrects and ends an ongoing rental arrangement', async () => {
    const user = userEvent.setup();
    const existing = {
      charged_rent_amount: '500.00',
      display_name: 'Whole home',
      effective_from: '2025-01-01',
      effective_to: null,
      frequency: 'WEEKLY',
      id: 'a57994c3-76a7-475f-ae76-bf17228f04b4',
      letting_fee: null,
      management_fee_rate: '8.0000',
      market_rent_amount: '550.00',
      notes: null,
      property_id: propertyId,
      rental_share_percentage: '100.0000',
      vacancy_rate: '5.0000',
    };
    let corrected: Record<string, unknown> | null = null;
    const fallback = standardFetch([summary], [existing]);
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(
            `/properties/${propertyId}/rental-profiles/${existing.id}`,
          ) &&
          init?.method === 'PATCH'
        ) {
          corrected = JSON.parse(init.body as string) as Record<
            string,
            unknown
          >;
          return Promise.resolve(response({ ...existing, ...corrected }));
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(
      await screen.findByRole('button', { name: 'Correct or end' }),
    );
    expect(screen.getByLabelText('Effective from')).toBeDisabled();
    fireEvent.change(
      screen.getByLabelText('Rent charged for this arrangement (NZD)'),
      { target: { value: '525' } },
    );
    fireEvent.change(screen.getByLabelText('Effective to'), {
      target: { value: '2025-06-30' },
    });
    await user.click(screen.getByRole('button', { name: 'Save correction' }));

    expect(
      await screen.findByText('Rental arrangement corrected'),
    ).toBeVisible();
    expect(corrected).toMatchObject({
      charged_rent_amount: '525',
      effective_to: '2025-06-30',
      rental_share_percentage: '100',
    });
  });

  it('shows backend-calculated rental cash flow and adds a property expense', async () => {
    const user = userEvent.setup();
    let saved: Record<string, unknown> | null = null;
    let cashflowRequests = 0;
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.includes(`/properties/${propertyId}/cashflow?`)) {
          cashflowRequests += 1;
        }
        if (
          path.endsWith(`/properties/${propertyId}/expenses`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          return Promise.resolve(
            response(
              {
                ...saved,
                id: '70534b12-fb69-41a2-9700-31f1c3123bd8',
                property_id: propertyId,
              },
              201,
            ),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(
      screen.getByRole('button', { name: 'Review rental finances' }),
    );
    expect(await screen.findByText('NZ$18,200.00')).toBeVisible();
    expect(screen.getByText('NZ$15,129.95')).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Rental cash-flow assumptions' }),
    ).toBeVisible();
    await user.click(
      screen.getByRole('button', { name: 'Add property expense' }),
    );
    fireEvent.change(screen.getByLabelText('Expense name'), {
      target: { value: 'Building insurance' },
    });
    await user.click(screen.getByLabelText('Expense type'));
    await user.click(screen.getByRole('option', { name: 'Insurance' }));
    fireEvent.change(screen.getByLabelText('Amount (NZD)'), {
      target: { value: '1200' },
    });
    fireEvent.change(screen.getByLabelText('Effective from'), {
      target: { value: '2026-01-01' },
    });
    await user.click(screen.getByRole('button', { name: 'Save expense' }));

    expect(await screen.findByText('Property expense added')).toBeVisible();
    expect(saved).toEqual({
      amount: '1200',
      display_name: 'Building insurance',
      effective_from: '2026-01-01',
      effective_to: null,
      expense_type_id: expenseTypeId,
      frequency: 'ANNUAL',
      is_rental_expense: false,
      notes: null,
    });
    await waitFor(() => expect(cashflowRequests).toBeGreaterThan(1));
  }, 30_000);

  it('does not offer creation to a view-only household member', async () => {
    const fallback = standardFetch();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith(`/households/${householdId}/access`)) {
          return Promise.resolve(
            response({ can_edit: false, can_manage: false, role: 'VIEWER' }),
          );
        }
        return fallback(input, init);
      }),
    );
    await renderPage();

    expect(
      await screen.findByText(/view-only access to properties/i),
    ).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Add property' })).toBeNull();
    expect(
      screen.queryByRole('button', { name: 'Add dated record' }),
    ).toBeNull();
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: 'View' }));
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Review rental finances' }));
    expect(
      screen.queryByRole('button', { name: 'Add ownership record' }),
    ).toBeNull();
    expect(
      screen.queryByRole('button', { name: 'Add rental arrangement' }),
    ).toBeNull();
    expect(
      screen.queryByRole('button', { name: 'Add property expense' }),
    ).toBeNull();
  });
});
