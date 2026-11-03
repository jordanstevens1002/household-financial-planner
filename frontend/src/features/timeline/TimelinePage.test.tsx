import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AnyRouter } from '@tanstack/react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createAppRouter } from '../../app/router';
import { selectionKeys } from '../../app/selectionStorage';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const householdId = '10000000-0000-4000-8000-000000000001';
const eventId = '10000000-0000-4000-8000-000000000002';
const eventTypeId = '10000000-0000-4000-8000-000000000003';
const userId = '10000000-0000-4000-8000-000000000004';
const propertyId = '10000000-0000-4000-8000-000000000005';

const event = {
  amount: '500000.00',
  classification: 'OBSERVED',
  created_by_user_id: userId,
  data_quality_flags: ['FUTURE_OBSERVED_EVENT'],
  effective_at: '2026-11-03T00:00:00Z',
  event_priority: 10,
  event_type_code: 'PROPERTY_VALUED',
  event_type_id: eventTypeId,
  household_id: householdId,
  id: eventId,
  idempotency_key: null,
  is_enabled: true,
  loan_id: null,
  notes: 'Independent valuation',
  payload: {},
  percentage: null,
  person_id: null,
  property_id: propertyId,
  recorded_at: '2026-11-03T01:00:00Z',
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

function fetcher(timelineStatus = 200) {
  return vi.fn<typeof fetch>((input) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(
        response({
          account: {
            display_name: 'Viewer',
            global_role: 'USER',
            id: userId,
            must_change_password: false,
            username: 'viewer',
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
    if (path.includes(`/households/${householdId}/timeline`))
      return Promise.resolve(
        timelineStatus === 200
          ? response({
              data_quality_flags: ['FUTURE_OBSERVED_EVENT'],
              events: [event],
              household_id: householdId,
            })
          : response({ detail: 'Timeline unavailable' }, timelineStatus),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
}

async function renderPage() {
  localStorage.setItem(selectionKeys.household, householdId);
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/timeline'] }),
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

describe('household timeline', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('loads the complete timeline with no query parameters', async () => {
    const mock = fetcher();
    vi.stubGlobal('fetch', mock);
    await renderPage();

    expect(await screen.findByText('Property Valued')).toBeVisible();
    expect(screen.getByText('Observed')).toBeVisible();
    expect(screen.getByText('Independent valuation')).toBeVisible();
    expect(
      screen.getByRole('button', {
        name: 'Data-quality notes: Future Observed Event',
      }),
    ).toBeVisible();
    expect(
      mock.mock.calls.some(
        ([input]) =>
          pathOf(input).endsWith(`/households/${householdId}/timeline`) &&
          !pathOf(input).includes('?'),
      ),
    ).toBe(true);
  });

  it('submits date and disabled-event filters explicitly', async () => {
    const user = userEvent.setup();
    const mock = fetcher();
    vi.stubGlobal('fetch', mock);
    await renderPage();
    await screen.findByText('Property Valued');

    await user.type(screen.getByLabelText('From'), '2026-01-01');
    await user.type(screen.getByLabelText('To'), '2026-12-31');
    await user.click(screen.getByLabelText('Include disabled events'));
    await user.click(screen.getByRole('button', { name: 'Refresh timeline' }));

    await waitFor(() =>
      expect(
        mock.mock.calls.some(([input]) => {
          const path = pathOf(input);
          return (
            path.includes('from_date=2026-01-01') &&
            path.includes('to_date=2026-12-31') &&
            path.includes('include_disabled=true')
          );
        }),
      ).toBe(true),
    );
  });

  it('blocks an inverted date range before requesting it', async () => {
    const user = userEvent.setup();
    const mock = fetcher();
    vi.stubGlobal('fetch', mock);
    await renderPage();
    await screen.findByText('Property Valued');
    const initialRequests = mock.mock.calls.length;

    await user.type(screen.getByLabelText('From'), '2027-01-01');
    await user.type(screen.getByLabelText('To'), '2026-01-01');

    expect(
      screen.getByText('From date must not be after to date.'),
    ).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Refresh timeline' }),
    ).toBeDisabled();
    expect(mock).toHaveBeenCalledTimes(initialRequests);
  });

  it('distinguishes request failure from an empty timeline', async () => {
    vi.stubGlobal('fetch', fetcher(503));
    await renderPage();

    expect(await screen.findByText('Timeline unavailable')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible();
    expect(screen.queryByText('No timeline events')).not.toBeInTheDocument();
  });
});
