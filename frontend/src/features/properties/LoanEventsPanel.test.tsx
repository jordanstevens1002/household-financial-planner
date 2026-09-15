import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { LoanEventsPanel } from './LoanEventsPanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ csrfToken: () => 'csrf-token' }),
}));

const householdId = '1bfbb15e-5293-4e29-95e0-f86b82e62528';
const loanId = '997d68f7-bf03-4f70-97bb-80cfe8619d09';
const rateTypeId = '9c466bd7-238f-49ad-92ed-cd1dd32ff660';
const loan = {
  account_reference_masked: null,
  borrower_person_ids: [],
  currency: 'NZD',
  display_name: 'Home loan',
  household_id: householdId,
  id: loanId,
  initial_interest_rate: '5.0000',
  interest_calculation_method: 'DAILY' as const,
  is_active: true,
  is_interest_only: false,
  lender: null,
  loan_group_id: null,
  loan_type_id: '951bd6cd-82db-4a37-a56f-95c36b02f9d1',
  notes: null,
  opening_balance: '300000.00',
  opening_balance_date: '2020-01-01',
  original_balance: null,
  property_id: '818badb5-2518-4c3f-8f6d-bb6ee750e606',
  repayment_frequency: 'MONTHLY' as const,
  scheduled_repayment: '2000.00',
  term_months: 360,
};
const eventTypes = [
  {
    code: 'LOAN_RATE_CHANGED',
    display_name: 'Rate changed',
    id: rateTypeId,
    is_active: true,
    priority: 1,
  },
  {
    code: 'PROPERTY_VALUED',
    display_name: 'Valued',
    id: 'property-event',
    is_active: true,
    priority: 2,
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

function renderPanel(canEdit = true) {
  return render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <LoanEventsPanel
            canEdit={canEdit}
            householdId={householdId}
            loans={[loan]}
          />
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
}

const recordedEvent = {
  amount: null,
  classification: 'OBSERVED',
  created_by_user_id: 'c034f21b-dd50-413e-a76d-16ce16a79c8c',
  data_quality_flags: [],
  effective_at: '2026-07-01T00:00:00Z',
  event_priority: 1,
  event_type_code: 'LOAN_RATE_CHANGED',
  event_type_id: rateTypeId,
  household_id: householdId,
  id: '660168bb-264e-475f-9a93-dba3bec036e6',
  idempotency_key: null,
  is_enabled: true,
  loan_id: loanId,
  notes: null,
  payload: {},
  percentage: '5.7500',
  person_id: null,
  property_id: loan.property_id,
  recorded_at: '2026-07-01T01:00:00Z',
};

describe('loan events', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows only the selected loan history to a viewer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/event-types'))
          return Promise.resolve(response(eventTypes));
        if (path.includes('/timeline'))
          return Promise.resolve(
            response({
              data_quality_flags: [],
              events: [
                recordedEvent,
                { ...recordedEvent, id: 'other', loan_id: 'other-loan' },
              ],
              household_id: householdId,
            }),
          );
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel(false);
    await user.click(screen.getByRole('button', { name: 'Loan events' }));

    const table = await screen.findByRole('table', {
      name: 'Loan event history',
    });
    expect(table).toHaveTextContent('Rate Changed');
    expect(table).toHaveTextContent('5.7500%');
    expect(screen.queryByRole('button', { name: 'Save event' })).toBeNull();
  });

  it('validates and saves a planned rate change', async () => {
    let saved: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/event-types'))
          return Promise.resolve(response(eventTypes));
        if (path.includes('/timeline'))
          return Promise.resolve(
            response({
              data_quality_flags: [],
              events: [],
              household_id: householdId,
            }),
          );
        if (path.endsWith(`/loans/${loanId}/events`)) {
          saved =
            typeof init?.body === 'string'
              ? (JSON.parse(init.body) as Record<string, unknown>)
              : null;
          return Promise.resolve(response(recordedEvent, 201));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole('button', { name: 'Loan events' }));
    await screen.findByText('No loan events');
    await user.click(screen.getByRole('button', { name: 'Save event' }));
    expect(await screen.findByText('Choose a loan event type')).toBeVisible();
    await user.click(screen.getByRole('combobox', { name: 'Change type' }));
    await user.click(
      await screen.findByRole('option', { name: 'Rate Changed' }),
    );
    await user.click(screen.getByRole('combobox', { name: 'Classification' }));
    await user.click(
      await screen.findByRole('option', { name: 'Planned — considering' }),
    );
    await user.type(
      screen.getByRole('textbox', { name: 'Annual interest rate %' }),
      '5.25',
    );
    await user.click(screen.getByRole('button', { name: 'Save event' }));

    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved).toMatchObject({
      amount: null,
      classification: 'PLANNED',
      event_type_id: rateTypeId,
      is_enabled: true,
      payload: {},
      percentage: '5.25',
    });
    expect(await screen.findByText('Loan event added')).toBeVisible();
  });
});
