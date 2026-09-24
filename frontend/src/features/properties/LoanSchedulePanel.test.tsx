import { CssBaseline, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { appTheme } from '../../app/theme';
import type { components } from '../../api/schema';
import { LoanSchedulePanel } from './LoanSchedulePanel';

const loanId = '997d68f7-bf03-4f70-97bb-80cfe8619d09';
const loan: components['schemas']['LoanRead'] = {
  account_reference_masked: null,
  borrower_person_ids: [],
  currency: 'NZD',
  display_name: 'Home loan',
  household_id: '1bfbb15e-5293-4e29-95e0-f86b82e62528',
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
  opening_balance_date: '2026-01-01',
  original_balance: null,
  property_id: '818badb5-2518-4c3f-8f6d-bb6ee750e606',
  repayment_frequency: 'MONTHLY' as const,
  scheduled_repayment: '2000.00',
  term_months: 360,
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': 'schedule-test',
    },
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

function renderPanel(loans = [loan]) {
  return render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <LoanSchedulePanel loans={loans} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

const entries = Array.from({ length: 26 }, (_, index) => ({
  annual_interest_rate: '5.0000',
  closing_balance: String(300000 - (index + 1) * 1000),
  interest: '1250.00',
  offset_balance: index ? '10000.00' : '0.00',
  opening_balance: String(300000 - index * 1000),
  payment_date: new Date(Date.UTC(2026, index, 1)).toISOString().slice(0, 10),
  payment_number: index + 1,
  principal: '1000.00',
  repayment: '2250.00',
}));

const schedule = {
  data_quality_flags: ['DAILY_INTEREST_USES_ACTUAL_365_BASIS'],
  entries,
  entry_limit: 25,
  entry_offset: 0,
  entry_total: entries.length,
  has_more: true,
  interest_saved_vs_no_offset: '4500.00',
  loan_id: loanId,
  payoff_date: '2051-01-01',
  remaining_balance: '274000.00',
  total_interest: '125000.00',
  total_repayments: '425000.00',
};

describe('loan schedule analysis', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('shows backend totals, assumptions, warnings and paged balance progression', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const request = new URL(pathOf(input), 'http://localhost');
        const offset = Number(request.searchParams.get('entry_offset') ?? 0);
        const pageEntries = entries.slice(offset, offset + 25);
        return Promise.resolve(
          response({
            ...schedule,
            entries: pageEntries,
            entry_offset: offset,
            has_more: offset + pageEntries.length < entries.length,
          }),
        );
      }),
    );
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Analyse schedule' }));

    expect(await screen.findByText('NZ$425,000.00')).toBeVisible();
    expect(screen.getByText('NZ$125,000.00')).toBeVisible();
    expect(screen.getByText('NZ$274,000.00')).toBeVisible();
    expect(screen.getByText('NZ$4,500.00')).toBeVisible();
    expect(screen.getByText(/opening balance NZ\$300,000\.00/)).toBeVisible();
    expect(
      screen.getByLabelText(
        'Schedule warnings: DAILY_INTEREST_USES_ACTUAL_365_BASIS',
      ),
    ).toBeVisible();
    expect(screen.getByText('Page 1 of 2 · 26 payments')).toBeVisible();
    expect(
      screen.getByRole('table', { name: 'Loan balance progression' }),
    ).toHaveTextContent('NZ$299,000.00');

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('Page 2 of 2 · 26 payments')).toBeVisible();
    expect(
      screen.getByRole('table', { name: 'Loan balance progression' }),
    ).toHaveTextContent('26');
    expect(
      pathOf(vi.mocked(fetch).mock.calls.at(-1)?.[0] as RequestInfo),
    ).toContain('entry_offset=25');
  });

  it('recovers a non-projectable loan by applying a bounded through date', async () => {
    const requested: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        requested.push(path);
        if (!path.includes('through_date='))
          return Promise.resolve(
            response(
              {
                detail:
                  'A loan term or through_date is required to generate a schedule',
              },
              422,
            ),
          );
        return Promise.resolve(
          response({
            ...schedule,
            entries: [],
            entry_total: 0,
            has_more: false,
            payoff_date: null,
          }),
        );
      }),
    );
    const user = userEvent.setup();
    renderPanel([{ ...loan, term_months: null }]);

    await user.click(screen.getByRole('button', { name: 'Analyse schedule' }));
    expect(
      await screen.findByText(/loan term or through_date is required/),
    ).toBeVisible();
    await user.type(screen.getByLabelText('Calculate through'), '2028-12-31');
    await user.click(screen.getByRole('button', { name: 'Calculate' }));

    expect(
      await screen.findByText('No scheduled payments occur in this period.'),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        requested.some((path) => path.includes('through_date=2028-12-31')),
      ).toBe(true),
    );
    expect(screen.getByText('Not paid off in this period')).toBeVisible();
  });
});
