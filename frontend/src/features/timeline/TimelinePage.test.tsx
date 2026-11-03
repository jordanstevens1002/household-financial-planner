import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AnyRouter } from '@tanstack/react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { components } from '../../api/schema';
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
type TimelineEvent = components['schemas']['FinancialEventRead'];

const event: TimelineEvent = {
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

function fetcher(
  timelineStatus = 200,
  events: TimelineEvent[] = [event],
  flags: string[] = ['FUTURE_OBSERVED_EVENT'],
) {
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
    if (path.endsWith('/access'))
      return Promise.resolve(
        response({
          can_administer: false,
          can_edit: true,
          can_manage_owners: false,
          can_view: true,
          role: 'EDITOR',
        }),
      );
    if (path.endsWith('/event-types'))
      return Promise.resolve(
        response([
          {
            code: 'PROPERTY_VALUED',
            display_name: 'Property valued',
            id: eventTypeId,
            is_active: true,
            priority: 10,
          },
        ]),
      );
    if (
      path.endsWith('/people') ||
      path.endsWith('/properties') ||
      path.endsWith('/loans')
    )
      return Promise.resolve(response([]));
    if (path.endsWith('/events')) return Promise.resolve(response(event, 201));
    if (path.includes(`/households/${householdId}/timeline`))
      return Promise.resolve(
        timelineStatus === 200
          ? response({
              data_quality_flags: flags,
              events,
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

  it('presents each related-record scope and disabled state', async () => {
    vi.stubGlobal(
      'fetch',
      fetcher(
        200,
        [
          event,
          {
            ...event,
            data_quality_flags: [],
            id: '10000000-0000-4000-8000-000000000006',
            is_enabled: false,
            loan_id: '10000000-0000-4000-8000-000000000007',
            notes: null,
            property_id: null,
          },
          {
            ...event,
            id: '10000000-0000-4000-8000-000000000008',
            person_id: '10000000-0000-4000-8000-000000000009',
            property_id: null,
          },
          {
            ...event,
            id: '10000000-0000-4000-8000-000000000010',
            property_id: null,
          },
        ],
        ['FUTURE_OBSERVED_EVENT'],
      ),
    );
    await renderPage();

    expect(
      await screen.findByText('Loan · 10000000-0000-4000-8000-000000000007'),
    ).toBeVisible();
    expect(
      screen.getByText('Person · 10000000-0000-4000-8000-000000000009'),
    ).toBeVisible();
    expect(screen.getByText('Household')).toBeVisible();
    expect(screen.getByText('Disabled')).toBeVisible();
  });

  it('distinguishes an empty complete timeline from filtered results', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', fetcher(200, [], []));
    await renderPage();

    expect(
      await screen.findByText(
        'Events will appear here as household activity is recorded.',
      ),
    ).toBeVisible();
    await user.type(screen.getByLabelText('From'), '2026-01-01');
    await user.click(screen.getByRole('button', { name: 'Refresh timeline' }));
    expect(
      await screen.findByText('No events match the selected timeline filters.'),
    ).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(
      await screen.findByText(
        'Events will appear here as household activity is recorded.',
      ),
    ).toBeVisible();
  });

  it('creates an event and keeps specialist fields advanced', async () => {
    const user = userEvent.setup();
    const mock = fetcher();
    vi.stubGlobal('fetch', mock);
    await renderPage();
    await user.click(await screen.findByRole('button', { name: 'Add event' }));
    const dialog = await screen.findByRole('dialog', {
      name: 'Add timeline event',
    });
    await user.click(within(dialog).getByLabelText('Event type'));
    await user.click(
      await screen.findByRole('option', { name: 'Property valued' }),
    );
    await user.type(
      within(dialog).getByLabelText('Effective time (UTC)'),
      '2026-11-03T09:30',
    );
    await user.type(
      within(dialog).getByLabelText('Amount (optional)'),
      '550000',
    );
    expect(within(dialog).queryByLabelText('Payload (JSON)')).not.toBeVisible();
    await user.click(within(dialog).getByText('Advanced'));
    expect(within(dialog).getByLabelText('Payload (JSON)')).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Add event' }));

    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith('/events') &&
            init?.method === 'POST' &&
            typeof init.body === 'string' &&
            init.body.includes('550000'),
        ),
      ).toBe(true),
    );
  });
});
