import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { appTheme } from '../../app/theme';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { RepaymentOverridesPanel } from './RepaymentOverridesPanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ csrfToken: () => 'csrf-token' }),
}));

const householdId = '1bfbb15e-5293-4e29-95e0-f86b82e62528';
const loanId = '997d68f7-bf03-4f70-97bb-80cfe8619d09';
const secondLoanId = 'de20aad7-dbe4-4c88-b39a-f936e3f600e9';
const firstPersonId = 'a2342535-475d-4eb9-9257-acfdf704bb65';
const secondPersonId = 'b79316f7-04d9-4345-88a9-996fd6518d85';

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

const people = [
  {
    date_of_birth: null,
    display_name: 'Alex',
    effective_from: '2020-01-01',
    effective_to: null,
    household_id: householdId,
    id: firstPersonId,
    is_active: true,
  },
  {
    date_of_birth: null,
    display_name: 'Sam',
    effective_from: '2020-01-01',
    effective_to: null,
    household_id: householdId,
    id: secondPersonId,
    is_active: true,
  },
];

const loan = {
  account_reference_masked: null,
  borrower_person_ids: [firstPersonId, secondPersonId],
  currency: 'AUD',
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

function renderPanel(canEdit = true, loans = [loan]) {
  return render(
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
          <RepaymentOverridesPanel
            canEdit={canEdit}
            householdId={householdId}
            loans={loans}
          />
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
}

async function choose(label: string, option: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole('combobox', { name: label }));
  await user.click(await screen.findByRole('option', { name: option }));
}

describe('advanced repayment overrides', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows borrower defaults and dated history to a viewer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith(`/households/${householdId}/people`))
          return Promise.resolve(response(people));
        if (path.endsWith(`/loans/${loanId}/repayment-responsibilities`))
          return Promise.resolve(
            response([
              {
                effective_from: '2026-01-01',
                effective_to: '2026-06-30',
                id: 'b25dd779-761c-4909-a917-5e0e60b9d6e8',
                loan_id: loanId,
                notes: null,
                person_id: secondPersonId,
                responsibility_percentage: '100.00',
              },
            ]),
          );
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel(false);
    await user.click(
      screen.getByRole('button', { name: 'Advanced repayment overrides' }),
    );

    expect(
      await screen.findByText('Borrower defaults: Alex, Sam'),
    ).toBeVisible();
    const table = screen.getByRole('table', {
      name: 'Repayment override history',
    });
    expect(table).toHaveTextContent('Sam 100.00%');
    expect(screen.queryByRole('button', { name: 'Save override' })).toBeNull();
    expect(screen.getByText(/only an editor can add one/i)).toBeVisible();
  });

  it('validates an exact total and creates one atomic allocation set', async () => {
    let saved: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith(`/households/${householdId}/people`))
          return Promise.resolve(response(people));
        if (path.endsWith(`/loans/${loanId}/repayment-responsibilities`))
          return Promise.resolve(response([]));
        if (path.includes(`/loans/${loanId}/repayment-responsibilities/`)) {
          expect(
            new URL(path, 'http://localhost').searchParams.get('create_only'),
          ).toBe('true');
          if (typeof init?.body !== 'string')
            throw new TypeError('Expected a JSON request body');
          saved = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(
            response({
              effective_from: path.split('/').at(-1),
              effective_to: null,
              responsibilities: [],
              total_percentage: '100',
              warnings: [],
            }),
          );
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel();
    await user.click(
      screen.getByRole('button', { name: 'Advanced repayment overrides' }),
    );
    await screen.findByText('Borrower defaults: Alex, Sam');
    await choose('Person 1', 'Alex');
    await user.type(screen.getByRole('textbox', { name: 'Share %' }), '60');
    await user.click(screen.getByRole('button', { name: 'Save override' }));
    expect(
      await screen.findByText('Repayment allocations must total exactly 100%'),
    ).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Add person' }));
    await choose('Person 2', 'Sam');
    const shares = screen.getAllByRole('textbox', { name: 'Share %' });
    await user.type(shares[1]!, '40');
    await user.click(screen.getByRole('button', { name: 'Save override' }));

    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved).toMatchObject({
      allocations: [
        { person_id: firstPersonId, responsibility_percentage: '60' },
        { person_id: secondPersonId, responsibility_percentage: '40' },
      ],
      effective_to: null,
    });
    expect(await screen.findByText('Repayment override added')).toBeVisible();
  });

  it('resets the unsaved allocation draft when another loan is selected', async () => {
    const secondLoan = {
      ...loan,
      display_name: 'Investment loan',
      id: secondLoanId,
    };
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith(`/households/${householdId}/people`))
          return Promise.resolve(response(people));
        if (path.includes('/repayment-responsibilities'))
          return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel(true, [loan, secondLoan]);
    await user.click(
      screen.getByRole('button', { name: 'Advanced repayment overrides' }),
    );
    await screen.findByText('Borrower defaults: Alex, Sam');
    const originalDate = screen.getByLabelText('Effective from');
    const defaultDate = (originalDate as HTMLInputElement).value;
    await user.clear(originalDate);
    await user.type(originalDate, '2027-03-01');
    await choose('Person 1', 'Alex');
    await user.type(screen.getByRole('textbox', { name: 'Share %' }), '100');
    await user.type(
      screen.getByRole('textbox', { name: 'Notes (optional)' }),
      'Draft note',
    );

    await choose('Loan', 'Investment loan');

    expect(screen.getByLabelText('Effective from')).toHaveValue(defaultDate);
    expect(
      screen.getByRole('combobox', { name: 'Person 1' }),
    ).not.toHaveTextContent('Alex');
    expect(screen.getByRole('textbox', { name: 'Share %' })).toHaveValue('');
    expect(
      screen.getByRole('textbox', { name: 'Notes (optional)' }),
    ).toHaveValue('');
  });

  it('keeps creation unavailable until failed history can be retried', async () => {
    let historyAttempts = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith(`/households/${householdId}/people`))
          return Promise.resolve(response(people));
        if (path.endsWith(`/loans/${loanId}/repayment-responsibilities`)) {
          historyAttempts += 1;
          return Promise.resolve(
            historyAttempts === 1
              ? response({ detail: 'Unavailable' }, 503)
              : response([]),
          );
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel();
    await user.click(
      screen.getByRole('button', { name: 'Advanced repayment overrides' }),
    );
    expect(
      await screen.findByText(/Repayment overrides could not be loaded/),
    ).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Save override' }),
    ).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('No dated overrides')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Save override' })).toBeEnabled();
  });
});
