import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createMemoryHistory, RouterProvider } from '@tanstack/react-router';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { AnyRouter } from '@tanstack/react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createAppRouter } from '../../app/router';
import { selectionKeys } from '../../app/selectionStorage';
import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthProvider } from '../auth/AuthProvider';

const householdId = '10000000-0000-4000-8000-000000000001';
const userId = '10000000-0000-4000-8000-000000000002';
const baseId = '10000000-0000-4000-8000-000000000003';
const childId = '10000000-0000-4000-8000-000000000004';
const eventId = '10000000-0000-4000-8000-000000000005';
const now = '2026-11-09T00:00:00Z';
const scenarios = [
  {
    base_scenario_id: null,
    created_at: now,
    description: 'Starting assumptions',
    display_name: 'Base plan',
    household_id: householdId,
    id: baseId,
    is_active: true,
    template_code: null,
    updated_at: now,
  },
  {
    base_scenario_id: baseId,
    created_at: now,
    description: null,
    display_name: 'Higher costs',
    household_id: householdId,
    id: childId,
    is_active: false,
    template_code: 'HIGHER_EXPENSES',
    updated_at: now,
  },
];
const templates = [
  {
    code: 'CUSTOM',
    default_value: '0',
    description: 'Create a scenario with custom overrides.',
    display_name: 'Custom',
    operation: 'SET',
    override_key: 'custom_metric',
    target_entity_type: 'METRIC',
  },
  {
    code: 'HIGHER_EXPENSES',
    default_value: '10',
    description: 'Increase annual household expenses by a percentage.',
    display_name: 'Higher household expenses',
    operation: 'MULTIPLY_PERCENT',
    override_key: 'annual_expenses',
    target_entity_type: 'METRIC',
  },
  {
    code: 'DELAYED_PROPERTY_PURCHASE',
    default_value: '90',
    description: 'Move a planned property-purchase event later.',
    display_name: 'Delayed property purchase',
    operation: 'SHIFT_DAYS',
    override_key: 'effective_at',
    target_entity_type: 'FINANCIAL_EVENT',
  },
];

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

function fetcher(canEdit = true, saved = scenarios, scenarioStatus = 200) {
  return vi.fn<typeof fetch>((input, init) => {
    const path = pathOf(input);
    if (path.endsWith('/auth/session'))
      return Promise.resolve(
        response({
          account: {
            display_name: 'Scenario user',
            global_role: 'USER',
            id: userId,
            must_change_password: false,
            username: 'scenario-user',
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
          can_edit: canEdit,
          can_manage_owners: false,
          can_view: true,
          role: canEdit ? 'EDITOR' : 'VIEWER',
        }),
      );
    if (path.endsWith('/scenario-templates'))
      return Promise.resolve(response(templates));
    if (path.includes('/timeline'))
      return Promise.resolve(
        response({
          data_quality_flags: [],
          events: [
            {
              classification: 'PLANNED',
              data_quality_flags: [],
              effective_at: '2027-01-15T00:00:00Z',
              event_type_code: 'PROPERTY_PURCHASED',
              id: eventId,
              is_enabled: true,
            },
            {
              classification: 'PLANNED',
              data_quality_flags: [],
              effective_at: '2027-01-16T00:00:00Z',
              event_type_code: 'INCOME_CHANGED',
              id: '10000000-0000-4000-8000-000000000006',
              is_enabled: true,
            },
            {
              classification: 'PROJECTED',
              data_quality_flags: [],
              effective_at: '2027-01-17T00:00:00Z',
              event_type_code: 'PROPERTY_PURCHASED',
              id: '10000000-0000-4000-8000-000000000007',
              is_enabled: true,
            },
            {
              classification: 'PLANNED',
              data_quality_flags: [],
              effective_at: '2027-01-18T00:00:00Z',
              event_type_code: 'PROPERTY_PURCHASED',
              id: '10000000-0000-4000-8000-000000000008',
              is_enabled: false,
            },
          ],
          household_id: householdId,
        }),
      );
    if (path.endsWith('/scenarios') && init?.method === 'POST')
      return Promise.resolve(response(scenarios[0], 201));
    if (path.endsWith('/scenarios/from-template') && init?.method === 'POST')
      return Promise.resolve(response(scenarios[1], 201));
    if (path.endsWith('/scenarios'))
      return Promise.resolve(
        scenarioStatus === 200
          ? response(saved)
          : response({ detail: 'Scenarios unavailable' }, scenarioStatus),
      );
    throw new Error(`Unexpected request: ${path}`);
  });
}

async function renderPage() {
  localStorage.setItem(selectionKeys.household, householdId);
  const router = createAppRouter();
  router.update({
    history: createMemoryHistory({ initialEntries: ['/scenarios'] }),
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

describe('saved scenario catalogue', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('shows saved template and inheritance context to a viewer', async () => {
    vi.stubGlobal('fetch', fetcher(false));
    await renderPage();

    expect(await screen.findAllByText('Base plan')).toHaveLength(2);
    expect(screen.getByText('Higher costs')).toBeVisible();
    expect(screen.getByText('Higher household expenses')).toBeVisible();
    expect(screen.getByText('Inactive')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Add scenario' })).toBeNull();
  });

  it('validates and creates a custom scenario with inheritance', async () => {
    const user = userEvent.setup();
    const mock = fetcher();
    vi.stubGlobal('fetch', mock);
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Add scenario' }),
    );
    const dialog = screen.getByRole('dialog', { name: 'Add scenario' });
    await user.click(
      within(dialog).getByRole('button', { name: 'Create scenario' }),
    );
    expect(within(dialog).getByText('Name is required.')).toBeVisible();
    await user.type(within(dialog).getByLabelText('Scenario name'), 'My plan');
    await user.click(within(dialog).getByLabelText('Inherits from (optional)'));
    await user.click(screen.getByRole('option', { name: 'Base plan' }));
    await user.click(
      within(dialog).getByRole('button', { name: 'Create scenario' }),
    );

    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith('/scenarios') &&
            init?.method === 'POST' &&
            typeof init.body === 'string' &&
            init.body.includes('My plan') &&
            init.body.includes(baseId),
        ),
      ).toBe(true),
    );
  });

  it('creates an event-targeted template scenario', async () => {
    const user = userEvent.setup();
    const mock = fetcher();
    vi.stubGlobal('fetch', mock);
    await renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Add scenario' }),
    );
    const dialog = screen.getByRole('dialog', { name: 'Add scenario' });
    await user.click(within(dialog).getByLabelText('Starting point'));
    await user.click(
      screen.getByRole('option', { name: 'Delayed property purchase' }),
    );
    await user.type(
      within(dialog).getByLabelText('Scenario name'),
      'Buy later',
    );
    await user.click(within(dialog).getByLabelText('Planned event'));
    const eventOptions = screen.getAllByRole('option');
    expect(eventOptions).toHaveLength(1);
    const eventOption = eventOptions[0];
    expect(eventOption).toBeDefined();
    if (!eventOption) throw new Error('Compatible planned event missing');
    expect(eventOption).toHaveTextContent('Property Purchased');
    await user.click(eventOption);
    await user.type(
      within(dialog).getByLabelText('Template value (optional)'),
      '1.5',
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Create scenario' }),
    );
    expect(
      within(dialog).getByText('Template value must be a whole number.'),
    ).toBeVisible();
    await user.clear(
      within(dialog).getByLabelText('Template value (optional)'),
    );
    await user.type(
      within(dialog).getByLabelText('Template value (optional)'),
      '120',
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Create scenario' }),
    );

    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([input, init]) =>
            pathOf(input).endsWith('/scenarios/from-template') &&
            init?.method === 'POST' &&
            typeof init.body === 'string' &&
            init.body.includes('DELAYED_PROPERTY_PURCHASE') &&
            init.body.includes(eventId) &&
            init.body.includes('120'),
        ),
      ).toBe(true),
    );
  });

  it('presents an empty saved catalogue', async () => {
    vi.stubGlobal('fetch', fetcher(true, []));
    await renderPage();
    expect(await screen.findByText('No saved scenarios')).toBeVisible();
    expect(screen.getByText(/Add a custom scenario/)).toBeVisible();
  });

  it('reports scenario catalogue failures with recovery', async () => {
    vi.stubGlobal('fetch', fetcher(true, [], 503));
    await renderPage();
    expect(await screen.findByText(/Scenarios unavailable/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible();
    expect(screen.queryByText('No saved scenarios')).toBeNull();
  });
});
