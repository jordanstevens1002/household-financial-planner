import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { appTheme } from '../../app/theme';
import type { components } from '../../api/schema';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { LoanTargetsPanel } from './LoanTargetsPanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ csrfToken: () => 'csrf-token' }),
}));

const householdId = '1bfbb15e-5293-4e29-95e0-f86b82e62528';
const loanId = '997d68f7-bf03-4f70-97bb-80cfe8619d09';
const goalTypeId = '951bd6cd-82db-4a37-a56f-95c36b02f9d1';
const comfortableGoalId = '4b640e69-b982-4612-a4de-96f9bfca0191';
const tightGoalId = '55c01216-44d6-4199-a45f-10a6a4617184';

const loan: components['schemas']['LoanRead'] = {
  account_reference_masked: null,
  borrower_person_ids: [],
  currency: 'NZD',
  display_name: 'Home loan',
  household_id: householdId,
  id: loanId,
  initial_interest_rate: '5.0000',
  interest_calculation_method: 'DAILY',
  is_active: true,
  is_interest_only: false,
  lender: null,
  loan_group_id: null,
  loan_type_id: '3dd428e8-ccbf-42ca-84c0-7174b0f28947',
  notes: null,
  opening_balance: '300000.00',
  opening_balance_date: '2026-01-01',
  original_balance: null,
  property_id: '818badb5-2518-4c3f-8f6d-bb6ee750e606',
  repayment_frequency: 'MONTHLY',
  scheduled_repayment: '2000.00',
  term_months: 360,
};

const goals: components['schemas']['GoalRead'][] = [
  {
    display_name: 'Comfortable payment',
    goal_type_id: goalTypeId,
    household_id: householdId,
    id: comfortableGoalId,
    is_active: true,
    loan_id: loanId,
    notes: null,
    person_id: null,
    priority: 1,
    property_id: null,
    target_amount: '700.00',
    target_boolean: null,
    target_date: null,
    target_percentage: null,
  },
  {
    display_name: 'Tighter payment',
    goal_type_id: goalTypeId,
    household_id: householdId,
    id: tightGoalId,
    is_active: true,
    loan_id: loanId,
    notes: null,
    person_id: null,
    priority: 2,
    property_id: null,
    target_amount: '400.00',
    target_boolean: null,
    target_date: null,
    target_percentage: null,
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
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <NotificationProvider>
          <LoanTargetsPanel
            canEdit={canEdit}
            householdId={householdId}
            loans={[loan]}
          />
        </NotificationProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

function catalogueResponse(input: RequestInfo | URL) {
  const path = pathOf(input);
  if (path.endsWith(`/households/${householdId}/goals`))
    return Promise.resolve(response(goals));
  if (path.endsWith('/lookups/goal_type'))
    return Promise.resolve(
      response([
        {
          code: 'MAXIMUM_WEEKLY_REPAYMENT',
          display_name: 'Maximum weekly repayment',
          id: goalTypeId,
          is_active: true,
        },
      ]),
    );
  throw new Error(`Unexpected request: ${path}`);
}

describe('loan targets and repayment comfort', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('calculates achievable and above-target results using the API', async () => {
    const calculations: Record<string, unknown>[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/target-calculation')) {
          const body = JSON.parse(init?.body as string) as Record<
            string,
            unknown
          >;
          calculations.push(body);
          const within = body.goal_id === comfortableGoalId;
          return Promise.resolve(
            response({
              estimated_payoff_date: '2051-01-01',
              goal_id: body.goal_id,
              loan_id: loanId,
              repayment_frequency: 'MONTHLY',
              required_repayment: '2600.00',
              target_amount: within ? '700.00' : '400.00',
              within_target: within,
            }),
          );
        }
        return catalogueResponse(input);
      }),
    );
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Loan targets' }));
    expect(
      await screen.findByRole('table', { name: 'Household loan targets' }),
    ).toHaveTextContent('NZ$700.00');

    await user.click(screen.getByLabelText('Saved target'));
    await user.click(
      screen.getByRole('option', { name: 'Comfortable payment' }),
    );
    await user.click(screen.getByRole('button', { name: 'Calculate' }));
    expect(await screen.findByText('Within your target')).toBeVisible();
    expect(
      screen.getByText(/Required monthly repayment: NZ\$2,600.00/),
    ).toBeVisible();

    await user.click(screen.getByLabelText('Saved target'));
    await user.click(screen.getByRole('option', { name: 'Tighter payment' }));
    await user.click(screen.getByRole('button', { name: 'Calculate' }));
    expect(await screen.findByText('Above your target')).toBeVisible();
    expect(calculations).toHaveLength(2);
    expect(calculations[1]).toMatchObject({ goal_id: tightGoalId });
  });

  it('creates a validated loan-specific target and refreshes the list', async () => {
    let saved: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (
          path.endsWith(`/households/${householdId}/goals`) &&
          init?.method === 'POST'
        ) {
          saved = JSON.parse(init.body as string) as Record<string, unknown>;
          return Promise.resolve(
            response({ ...goals[0], ...saved, id: comfortableGoalId }, 201),
          );
        }
        return catalogueResponse(input);
      }),
    );
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Loan targets' }));
    await user.click(await screen.findByRole('button', { name: 'Add target' }));
    const dialog = screen.getByRole('dialog', { name: 'Add a loan target' });
    await user.type(
      within(dialog).getByLabelText('Target name'),
      'Our comfort',
    );
    await user.type(
      within(dialog).getByLabelText('Maximum comfortable weekly repayment'),
      '650.50',
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Save target' }),
    );

    expect(await screen.findByText('Loan target added')).toBeVisible();
    expect(saved).toMatchObject({
      display_name: 'Our comfort',
      goal_type_id: goalTypeId,
      loan_id: loanId,
      priority: 0,
      target_amount: '650.50',
    });
  });

  it('keeps creation unavailable to viewers and offers retry on load failure', async () => {
    let attempts = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        if (pathOf(input).endsWith(`/households/${householdId}/goals`)) {
          attempts += 1;
          return Promise.resolve(
            attempts === 1
              ? response({ detail: 'Unavailable' }, 503)
              : response(goals),
          );
        }
        return catalogueResponse(input);
      }),
    );
    const user = userEvent.setup();
    renderPanel(false);

    await user.click(screen.getByRole('button', { name: 'Loan targets' }));
    expect(
      await screen.findByText(/Loan targets could not be loaded/),
    ).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(
      await screen.findByRole('table', { name: 'Household loan targets' }),
    ).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Add target' })).toBeNull();
  });
});
