import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { appTheme } from '../../app/theme';
import type { components } from '../../api/schema';
import { NotificationProvider } from '../../shared/NotificationProvider';
import { LoanRefinancePanel } from './LoanRefinancePanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ csrfToken: () => 'csrf-token' }),
}));

const householdId = '1bfbb15e-5293-4e29-95e0-f86b82e62528';
const propertyId = '818badb5-2518-4c3f-8f6d-bb6ee750e606';
const loanId = '997d68f7-bf03-4f70-97bb-80cfe8619d09';
const loanTypeId = '951bd6cd-82db-4a37-a56f-95c36b02f9d1';
const groupId = '47cf84d0-3151-4b75-9667-e5daa7e822d9';
const borrowerId = 'a2342535-475d-4eb9-9257-acfdf704bb65';

const activeLoan: components['schemas']['LoanRead'] = {
  account_reference_masked: null,
  borrower_person_ids: [borrowerId],
  currency: 'NZD',
  display_name: 'Current mortgage',
  household_id: householdId,
  id: loanId,
  initial_interest_rate: '5.7500',
  interest_calculation_method: 'DAILY',
  is_active: true,
  is_interest_only: false,
  lender: 'Old lender',
  loan_group_id: groupId,
  loan_type_id: loanTypeId,
  notes: null,
  opening_balance: '310000.00',
  opening_balance_date: '2026-06-30',
  original_balance: '320000.00',
  property_id: propertyId,
  repayment_frequency: 'MONTHLY',
  scheduled_repayment: '2100.00',
  term_months: 360,
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

function renderPanel(canEdit = true, loans = [activeLoan]) {
  return render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <NotificationProvider>
          <LoanRefinancePanel
            canEdit={canEdit}
            householdId={householdId}
            loans={loans}
            propertyId={propertyId}
          />
        </NotificationProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

function catalogue(input: RequestInfo | URL) {
  if (pathOf(input).endsWith('/lookups/loan_type')) {
    return Promise.resolve(
      response([
        {
          code: 'HOME_LOAN',
          display_name: 'Home loan',
          id: loanTypeId,
          is_active: true,
        },
      ]),
    );
  }
  throw new Error(`Unexpected request: ${pathOf(input)}`);
}

describe('loan refinancing', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('reviews and records an observed replacement while preserving associations', async () => {
    let saved: Record<string, unknown> | null = null;
    let savedIdempotencyKey: unknown;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        if (pathOf(input).endsWith(`/loans/${loanId}/refinance`)) {
          saved = JSON.parse(init?.body as string) as Record<string, unknown>;
          savedIdempotencyKey = saved.idempotency_key;
          const replacement = (saved.replacement_loan ?? {}) as Record<
            string,
            unknown
          >;
          return Promise.resolve(
            response(
              {
                closed_loan_id: loanId,
                refinance_event: { effective_at: '2026-09-27T00:00:00Z' },
                replacement_loan: {
                  ...activeLoan,
                  ...replacement,
                  id: '13dfb7c8-2fd1-48b5-98ec-bc83c6d24585',
                },
              },
              201,
            ),
          );
        }
        return catalogue(input);
      }),
    );
    renderPanel();

    fireEvent.click(screen.getByRole('button', { name: 'Record refinance' }));
    const dialog = screen.getByRole('dialog', {
      name: 'Record a completed refinance',
    });
    expect(
      within(dialog).getByText(
        /property, split group, currency and 1 borrower/i,
      ),
    ).toBeVisible();
    fireEvent.change(within(dialog).getByLabelText('Refinance date'), {
      target: { value: '2026-09-27' },
    });
    fireEvent.change(within(dialog).getByLabelText('Replacement loan name'), {
      target: { value: 'Better mortgage' },
    });
    fireEvent.change(within(dialog).getByLabelText('New lender (optional)'), {
      target: { value: 'New lender' },
    });
    fireEvent.change(
      within(dialog).getByLabelText('Payout or opening balance (NZD)'),
      { target: { value: '295000.50' } },
    );
    fireEvent.change(within(dialog).getByLabelText('Annual interest rate %'), {
      target: { value: '4.9000' },
    });
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Review refinance' }),
    );
    expect(
      await screen.findByRole('dialog', {
        name: 'Confirm completed refinance',
      }),
    ).toHaveTextContent('Current mortgage');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(saved).toBeNull();
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Confirm completed refinance' }),
      ).toBeNull(),
    );
    const reopenedDialog = screen.getByRole('dialog', {
      name: 'Record a completed refinance',
    });
    fireEvent.click(
      within(reopenedDialog).getByRole('button', { name: 'Review refinance' }),
    );
    const secondConfirmation = await screen.findByRole('dialog', {
      name: 'Confirm completed refinance',
    });
    fireEvent.click(
      within(secondConfirmation).getByRole('button', {
        name: 'Record refinance',
      }),
    );

    expect(await screen.findByText('Refinance recorded')).toBeVisible();
    expect(saved).toMatchObject({
      effective_at: '2026-09-27T00:00:00Z',
      replacement_loan: {
        borrower_person_ids: [borrowerId],
        display_name: 'Better mortgage',
        is_active: true,
        loan_group_id: groupId,
        opening_balance: '295000.50',
        opening_balance_date: '2026-09-27',
        property_id: propertyId,
      },
    });
    expect(typeof savedIdempotencyKey).toBe('string');
    expect(
      await screen.findByText(/Better mortgage was created/),
    ).toBeVisible();
  });

  it('reuses its idempotency key when an ambiguous failure is retried', async () => {
    const attempts: Record<string, unknown>[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        if (pathOf(input).endsWith(`/loans/${loanId}/refinance`)) {
          const payload = JSON.parse(init?.body as string) as Record<
            string,
            unknown
          >;
          attempts.push(payload);
          if (attempts.length === 1) {
            return Promise.resolve(
              response({ detail: 'Gateway timeout' }, 504),
            );
          }
          return Promise.resolve(
            response(
              {
                closed_loan_id: loanId,
                refinance_event: { effective_at: '2026-09-27T00:00:00Z' },
                replacement_loan: {
                  ...activeLoan,
                  ...(payload.replacement_loan as Record<string, unknown>),
                  id: '13dfb7c8-2fd1-48b5-98ec-bc83c6d24585',
                },
              },
              201,
            ),
          );
        }
        return catalogue(input);
      }),
    );
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Record refinance' }));
    const dialog = screen.getByRole('dialog', {
      name: 'Record a completed refinance',
    });
    fireEvent.change(within(dialog).getByLabelText('Refinance date'), {
      target: { value: '2026-09-27' },
    });
    await user.click(
      within(dialog).getByRole('button', { name: 'Review refinance' }),
    );
    const confirmation = screen.getByRole('dialog', {
      name: 'Confirm completed refinance',
    });
    await user.click(
      within(confirmation).getByRole('button', { name: 'Record refinance' }),
    );
    expect(
      (await screen.findAllByText(/Gateway timeout/)).length,
    ).toBeGreaterThan(0);
    await user.click(
      within(confirmation).getByRole('button', { name: 'Record refinance' }),
    );

    expect(await screen.findByText('Refinance recorded')).toBeVisible();
    expect(attempts).toHaveLength(2);
    expect(attempts[0]?.idempotency_key).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(attempts[1]?.idempotency_key).toBe(attempts[0]?.idempotency_key);
  });

  it('blocks invalid financial values before confirmation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => catalogue(input)),
    );
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole('button', { name: 'Record refinance' }));
    const dialog = screen.getByRole('dialog', {
      name: 'Record a completed refinance',
    });
    fireEvent.change(
      within(dialog).getByLabelText('Payout or opening balance (NZD)'),
      { target: { value: '1e9' } },
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Review refinance' }),
    );
    expect(
      await within(dialog).findByText('Enter a valid payout balance'),
    ).toBeVisible();
    expect(
      screen.queryByRole('dialog', { name: 'Confirm completed refinance' }),
    ).toBeNull();
  });

  it('is unavailable to viewers and when every loan is closed', () => {
    const { rerender } = renderPanel(false);
    expect(
      screen.queryByRole('button', { name: 'Record refinance' }),
    ).toBeNull();
    rerender(
      <ThemeProvider theme={appTheme}>
        <QueryClientProvider client={new QueryClient()}>
          <NotificationProvider>
            <LoanRefinancePanel
              canEdit
              householdId={householdId}
              loans={[{ ...activeLoan, is_active: false }]}
              propertyId={propertyId}
            />
          </NotificationProvider>
        </QueryClientProvider>
      </ThemeProvider>,
    );
    expect(
      screen.queryByRole('button', { name: 'Record refinance' }),
    ).toBeNull();
  });
});
