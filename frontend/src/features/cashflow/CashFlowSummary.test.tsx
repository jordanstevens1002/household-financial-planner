import { ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { appTheme } from '../../app/theme';
import { CashFlowSummary } from './CashFlowSummary';

const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const projection = {
  annual_expenses: '42000.00',
  annual_gross_income: '100000.00',
  annual_loan_repayments: '36000.00',
  annual_net_income: '80000.00',
  annual_ordinary_expenses: '6000.00',
  annual_surplus: '38000.00',
  as_of: '2026-08-02',
  currency: 'NZD',
  household_id: householdId,
  loan_repayments: [
    {
      allocations: [
        {
          annual_amount: '36000.00',
          display_name: 'Alex Planner',
          monthly_amount: '3000.00',
          person_id: '85e30193-a324-4d22-9065-e25d819f6530',
          responsibility_percentage: '100.00',
        },
      ],
      annual_repayment: '36000.00',
      currency: 'NZD',
      display_name: 'Home loan',
      included_in_household_total: true,
      loan_id: 'b9a6023d-6cc1-4ea8-b100-15fc9d488a0f',
      monthly_repayment: '3000.00',
      periodic_repayment: '1384.62',
      property_id: null,
      repayment_frequency: 'FORTNIGHTLY',
      warnings: ['Inactive payer remains historically responsible.'],
    },
  ],
  monthly_expenses: '3500.00',
  monthly_loan_repayments: '3000.00',
  monthly_net_income: '6666.67',
  monthly_ordinary_expenses: '500.00',
  monthly_surplus: '3166.67',
  people: [
    {
      calculation_mode: 'AUTOMATIC',
      display_name: 'Alex Planner',
      gross_taxable_income: '100000.00',
      net_income: '80000.00',
      non_taxable_income: '0.00',
      person_id: '85e30193-a324-4d22-9065-e25d819f6530',
      tax_and_repayments: '20000.00',
      warnings: ['Latest installed tax rules used for this future date.'],
    },
  ],
  warnings: ['Latest installed tax rules used for this future date.'],
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status,
  });
}

function renderSummary() {
  render(
    <ThemeProvider theme={appTheme}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <CashFlowSummary currency="NZD" householdId={householdId} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('household cash-flow summary', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('presents backend totals, tax provenance, repayments and warnings', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => Promise.resolve(response(projection))),
    );
    renderSummary();

    expect((await screen.findAllByText('NZ$80,000.00'))[0]).toBeVisible();
    expect(screen.getByText('NZ$38,000.00')).toBeVisible();
    expect(screen.getByText('NZ$3,166.67')).toBeVisible();
    expect(
      screen.getByText(/Alex Planner: Latest installed tax rules used/i),
    ).toBeVisible();
    const people = screen.getByRole('table', {
      name: 'Person cash-flow projections',
    });
    expect(people).toHaveTextContent('Alex Planner');
    expect(people).toHaveTextContent('AUTOMATIC');
    expect(people).toHaveTextContent('NZ$20,000.00');
    const loans = screen.getByRole('table', {
      name: 'Automatic loan repayments',
    });
    expect(loans).toHaveTextContent('Home loan');
    expect(loans).toHaveTextContent('NZ$3,000.00');
    expect(loans).toHaveTextContent('Alex Planner 100.00%');
    expect(loans).toHaveTextContent('Yes');
    expect(loans).toHaveTextContent(
      'Home loan: Inactive payer remains historically responsible.',
    );
    expect(screen.getByText('Results as of 2026-08-02.')).toBeVisible();
  });

  it('requests a newly selected position date', async () => {
    const user = userEvent.setup();
    const requested: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        requested.push(
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.href
              : input.url,
        );
        return Promise.resolve(response(projection));
      }),
    );
    renderSummary();
    await screen.findAllByText('NZ$80,000.00');
    const date = screen.getByLabelText('Position date');
    await user.clear(date);
    await user.type(date, '2028-07-01');
    await user.click(screen.getByRole('button', { name: 'Refresh position' }));
    await waitFor(() =>
      expect(requested.some((url) => url.includes('as_of=2028-07-01'))).toBe(
        true,
      ),
    );
  });

  it('refetches when refreshing the currently selected date', async () => {
    const user = userEvent.setup();
    const request = vi.fn<typeof fetch>(() =>
      Promise.resolve(response(projection)),
    );
    vi.stubGlobal('fetch', request);
    renderSummary();
    await screen.findByText('Results as of 2026-08-02.');

    await user.click(screen.getByRole('button', { name: 'Refresh position' }));

    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
  });

  it('marks edited dates as pending while retaining the result date', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => Promise.resolve(response(projection))),
    );
    renderSummary();
    await screen.findByText('Results as of 2026-08-02.');

    const date = screen.getByLabelText('Position date');
    await user.clear(date);
    await user.type(date, '2028-07-01');

    expect(screen.getByText(/position date has changed/i)).toBeVisible();
    expect(screen.getByText(/Results as of 2026-08-02/i)).toBeVisible();
  });

  it('validates the position date without discarding the current result', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(() => Promise.resolve(response(projection))),
    );
    renderSummary();
    await screen.findAllByText('NZ$80,000.00');
    await user.clear(screen.getByLabelText('Position date'));
    await user.click(screen.getByRole('button', { name: 'Refresh position' }));
    expect(screen.getByText('Use YYYY-MM-DD')).toBeVisible();
    expect(screen.getAllByText('NZ$80,000.00')[0]).toBeVisible();
  });

  it('shows a recoverable API error', async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response({ detail: 'Unavailable' }, 500))
      .mockResolvedValue(response(projection));
    vi.stubGlobal('fetch', fetchMock);
    renderSummary();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Unavailable');
    await user.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect((await screen.findAllByText('NZ$80,000.00'))[0]).toBeVisible();
  });
});
