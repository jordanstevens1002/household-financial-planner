import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { appTheme } from '../../app/theme';
import { PropertyStatePanel } from './PropertyStatePanel';

const householdId = '10000000-0000-4000-8000-000000000001';
const propertyId = '10000000-0000-4000-8000-000000000002';
const statusId = '10000000-0000-4000-8000-000000000003';
const property = {
  currency: 'AUD',
  current_status_id: statusId,
  current_value: '800000.00',
  display_name: 'Family home',
  id: propertyId,
  position_date: '2026-10-01',
  property_type_id: '10000000-0000-4000-8000-000000000004',
  purchase_date: '2020-01-01',
  purchase_price: '600000.00',
  setup_mode: 'CURRENT_SNAPSHOT',
  total_property_debt: '300000.00',
};
const resolved = {
  applied_event_ids: ['10000000-0000-4000-8000-000000000005'],
  as_of: '2026-11-01',
  baseline_date: '2026-10-01',
  baseline_id: '10000000-0000-4000-8000-000000000006',
  data_quality_flags: ['ESTIMATED_HISTORICAL_POSITION'],
  is_active_asset: true,
  loan_balance_total: '295000.00',
  property_id: propertyId,
  property_value: '820000.00',
  status_id: statusId,
  temporal_position: 'CURRENT',
  valuation_date: '2026-10-15',
  valuation_id: '10000000-0000-4000-8000-000000000007',
  valuation_is_estimate: true,
  valuation_type: 'USER_ESTIMATE',
};
const status = {
  applies_management_fee: null,
  applies_rental_expenses: null,
  applies_vacancy: null,
  category: 'property_status',
  code: 'OWNER_OCCUPIED',
  display_name: 'Owner occupied',
  generates_rental_income: false,
  id: statusId,
  is_active: true,
  is_active_asset: true,
  sort_order: 10,
};

const response = (body: unknown, responseStatus = 200) =>
  new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status: responseStatus,
  });

const pathOf = (input: RequestInfo | URL) =>
  typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.href
      : input.url;

function renderPanel() {
  render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: { queries: { retry: false } },
          })
        }
      >
        <PropertyStatePanel householdId={householdId} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('dated property position', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('renders backend-resolved values and hides them when inputs become stale', async () => {
    const user = userEvent.setup();
    const mock = vi.fn<typeof fetch>((input) => {
      const path = pathOf(input);
      if (path.endsWith('/property-summaries'))
        return Promise.resolve(response([property]));
      if (path.endsWith('/lookups/property_status'))
        return Promise.resolve(response([status]));
      if (path.includes(`/properties/${propertyId}/state`))
        return Promise.resolve(response(resolved));
      throw new Error(`Unexpected request: ${path}`);
    });
    vi.stubGlobal('fetch', mock);
    renderPanel();

    await user.click(await screen.findByLabelText('Property'));
    await user.click(screen.getByRole('option', { name: 'Family home' }));
    const date = screen.getByLabelText('Position date');
    await user.clear(date);
    await user.type(date, '2026-11-01');
    await user.click(screen.getByRole('button', { name: 'Resolve position' }));

    expect(await screen.findByText('$820,000.00')).toBeVisible();
    expect(screen.getByText('$295,000.00')).toBeVisible();
    expect(screen.getByText(/Owner occupied/)).toBeVisible();
    expect(screen.getByText(/Applied timeline events: 1/)).toBeVisible();
    expect(screen.getByText('Estimated Historical Position')).toBeVisible();

    await user.clear(date);
    await user.type(date, '2026-12-01');
    expect(
      screen.getByText(/Resolve the position to display results/),
    ).toBeVisible();
    expect(screen.queryByText('$820,000.00')).toBeNull();
    expect(
      mock.mock.calls.filter(([input]) =>
        pathOf(input).includes(`/properties/${propertyId}/state`),
      ),
    ).toHaveLength(1);
  });

  it('distinguishes an empty household from a property request failure', async () => {
    const user = userEvent.setup();
    let fail = true;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/property-summaries'))
          return Promise.resolve(
            fail
              ? response({ detail: 'Properties unavailable' }, 503)
              : response([]),
          );
        if (path.endsWith('/lookups/property_status'))
          return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();

    expect(await screen.findByText(/Properties unavailable/)).toBeVisible();
    fail = false;
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(
      await screen.findByText(/Add a property before resolving/),
    ).toBeVisible();
  });

  it('offers recovery when dated resolution fails', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/property-summaries'))
          return Promise.resolve(response([property]));
        if (path.endsWith('/lookups/property_status'))
          return Promise.resolve(response([status]));
        if (path.includes(`/properties/${propertyId}/state`))
          return Promise.resolve(
            response({ detail: 'Position unavailable' }, 503),
          );
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();

    await user.click(await screen.findByLabelText('Property'));
    await user.click(screen.getByRole('option', { name: 'Family home' }));
    await user.click(screen.getByRole('button', { name: 'Resolve position' }));

    expect(await screen.findByText(/Position unavailable/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible();
  });
});
