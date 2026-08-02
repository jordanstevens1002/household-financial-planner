import { ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { appTheme } from '../../app/theme';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import { TaxCalculatorPanel } from './TaxCalculatorPanel';
import { taxCalculationSchema } from './taxCalculationValidation';

const provider = {
  display_name: 'Example New Zealand tax',
  jurisdiction: 'NZ',
  supported_tax_years: ['2026'],
};
const authenticated: AuthContextValue = {
  account: {
    display_name: 'Tax User',
    email: null,
    global_role: 'USER',
    id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
    must_change_password: false,
    username: 'tax-user',
  },
  bootstrap: vi.fn(),
  changePassword: vi.fn(),
  csrfToken: vi.fn(() => 'csrf-token'),
  expired: false,
  loading: false,
  login: vi.fn(),
  logout: vi.fn(),
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

function renderPanel() {
  render(
    <ThemeProvider theme={appTheme}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <AuthContext.Provider value={authenticated}>
          <TaxCalculatorPanel />
        </AuthContext.Provider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe('standalone tax calculation', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('calculates with an explicitly selected provider and shows provenance', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(response([provider]));
        if (path.endsWith('/calculations/tax') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(
            response({
              components: [
                {
                  amount: '20000.00',
                  code: 'income_tax',
                  display_name: 'Income tax',
                },
              ],
              jurisdiction: 'NZ',
              net_income: '80000.00',
              ruleset_version: 'NZ-2026-example',
              tax_year: '2026',
              taxable_income: '100000.00',
              total: '20000.00',
              warnings: ['Example provider warning'],
            }),
          );
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPanel();
    const providerSelect = await screen.findByLabelText(
      'Provider and tax year',
    );
    expect(providerSelect).not.toHaveTextContent(provider.display_name);
    await user.type(screen.getByLabelText('Gross taxable income'), '100000');
    await user.click(providerSelect);
    await user.click(screen.getByText(`${provider.display_name} — 2026`));
    await user.click(screen.getByText('Advanced'));
    fireEvent.change(screen.getByLabelText('Provider settings as JSON'), {
      target: { value: '{"resident":true}' },
    });
    await user.click(
      screen.getByRole('button', { name: 'Calculate estimate' }),
    );

    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody).toEqual({
      gross_taxable_income: '100000',
      jurisdiction: 'NZ',
      settings: {
        calculation_mode: 'AUTOMATIC',
        parameters: { resident: true },
      },
      tax_year: '2026',
    });
    const result = await screen.findByLabelText('Tax estimate result');
    expect(result).toHaveTextContent(provider.display_name);
    expect(result).toHaveTextContent('NZ-2026-example');
    expect(result).toHaveTextContent('Example provider warning');
    expect(
      within(result).getByRole('table', { name: 'Tax estimate components' }),
    ).toHaveTextContent('Income tax');
  });

  it('keeps manual calculation available when provider discovery fails', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(response({ detail: 'Unavailable' }, 500));
        if (path.endsWith('/calculations/tax') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(
            response({
              components: [],
              jurisdiction: 'CA',
              net_income: '60000.00',
              ruleset_version: 'manual',
              tax_year: '2026',
              taxable_income: '80000.00',
              total: '20000.00',
              warnings: [
                'Manual net income used; tax components are not calculated.',
              ],
            }),
          );
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPanel();
    expect(
      await screen.findByText(/Installed tax providers could not be loaded/i),
    ).toBeVisible();
    await user.click(screen.getByText('Advanced'));
    fireEvent.change(screen.getByLabelText('Provider settings as JSON'), {
      target: { value: '{broken' },
    });
    await user.click(screen.getByLabelText('Calculation method'));
    await user.click(screen.getByText('Manual annual net income'));
    await user.type(screen.getByLabelText('Gross taxable income'), '80000');
    await user.type(screen.getByLabelText('Jurisdiction'), 'ca');
    await user.type(screen.getByLabelText('Tax year'), '2026');
    await user.type(screen.getByLabelText('Annual net income'), '60000');
    await user.click(
      screen.getByRole('button', { name: 'Calculate estimate' }),
    );

    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody).toMatchObject({
      gross_taxable_income: '80000',
      jurisdiction: 'CA',
      settings: {
        calculation_mode: 'MANUAL_NET',
        manual_annual_net_income: '60000',
      },
      tax_year: '2026',
    });
    const result = await screen.findByLabelText('Tax estimate result');
    expect(result).toHaveTextContent('CA (not currently discovered)');
    expect(result).toHaveTextContent('No component breakdown is available');
    expect(result).toHaveTextContent('Manual net income used');
  });

  it('shows API calculation failures without discarding the form', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(response([provider]));
        if (path.endsWith('/calculations/tax'))
          return Promise.resolve(response({ detail: 'Unsupported year' }, 422));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPanel();
    await user.type(screen.getByLabelText('Gross taxable income'), '90000');
    await user.click(await screen.findByLabelText('Provider and tax year'));
    await user.click(screen.getByText(`${provider.display_name} — 2026`));
    await user.click(
      screen.getByRole('button', { name: 'Calculate estimate' }),
    );

    expect(await screen.findByText(/Unsupported year/i)).toBeVisible();
    expect(screen.getByLabelText('Gross taxable income')).toHaveValue('90000');
  });
});

const validCalculation = {
  grossTaxableIncome: '100000',
  manualAnnualNetIncome: '',
  manualJurisdiction: '',
  manualTaxYear: '',
  mode: 'AUTOMATIC',
  parameters: '{}',
  providerYear: 'NZ|2026',
} as const;

describe('tax calculation validation', () => {
  it.each(['', ' ', '-1', 'not-a-number'])(
    'rejects gross income %j',
    (grossTaxableIncome) => {
      expect(
        taxCalculationSchema.safeParse({
          ...validCalculation,
          grossTaxableIncome,
        }).success,
      ).toBe(false);
    },
  );

  it('requires a provider only for automatic calculations', () => {
    expect(
      taxCalculationSchema.safeParse({
        ...validCalculation,
        providerYear: '',
      }).success,
    ).toBe(false);
    expect(
      taxCalculationSchema.safeParse({
        ...validCalculation,
        manualAnnualNetIncome: '60000',
        manualJurisdiction: 'CA',
        manualTaxYear: '2026',
        mode: 'MANUAL_NET',
        parameters: '{broken',
        providerYear: '',
      }).success,
    ).toBe(true);
  });
});
