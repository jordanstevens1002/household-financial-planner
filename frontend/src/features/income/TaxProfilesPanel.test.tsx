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
import { NotificationProvider } from '../../shared/NotificationProvider';
import { AuthContext, type AuthContextValue } from '../auth/AuthContext';
import { TaxProfilesPanel } from './TaxProfilesPanel';
import { taxProfileSchema } from './taxProfileValidation';

const personId = '85e30193-a324-4d22-9065-e25d819f6530';
const provider = {
  display_name: 'Example New Zealand tax',
  jurisdiction: 'NZ',
  supported_tax_years: ['2026'],
};
const automaticProfile = {
  effective_from: '2026-08-02',
  effective_to: null,
  id: 'cf140f96-a2b1-442f-b5f8-c21c123d7917',
  jurisdiction: 'NZ',
  person_id: personId,
  settings: {
    calculation_mode: 'AUTOMATIC',
    manual_annual_net_income: null,
    parameters: {},
  },
  tax_year: '2026',
};
const authenticated: AuthContextValue = {
  account: {
    display_name: 'Tax Editor',
    email: null,
    global_role: 'USER',
    id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
    must_change_password: false,
    username: 'tax-editor',
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

function renderPanel(canEdit = true) {
  render(
    <ThemeProvider theme={appTheme}>
      <NotificationProvider>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <AuthContext.Provider value={authenticated}>
            <TaxProfilesPanel canEdit={canEdit} personId={personId} />
          </AuthContext.Provider>
        </QueryClientProvider>
      </NotificationProvider>
    </ThemeProvider>,
  );
}

describe('tax profile workflows', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('lets a viewer read provider provenance without offering creation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(response([provider]));
        if (path.endsWith('/tax-profiles'))
          return Promise.resolve(response([automaticProfile]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPanel(false);

    const table = await screen.findByRole('table', { name: 'Tax settings' });
    expect(within(table).getByText(provider.display_name)).toBeVisible();
    expect(within(table).getByText('Installed provider')).toBeVisible();
    expect(screen.getByText(/view-only access/i)).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Add tax settings' }),
    ).toBeNull();
  });

  it('creates automatic settings from explicit provider discovery', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(response([provider]));
        if (path.endsWith('/tax-profiles') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(response(automaticProfile, 201));
        }
        if (path.endsWith('/tax-profiles'))
          return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPanel();
    await user.click(
      await screen.findByRole('button', { name: 'Add tax settings' }),
    );
    const providerSelect = await screen.findByLabelText(
      'Provider and tax year',
    );
    expect(providerSelect).not.toHaveTextContent(provider.display_name);
    await user.click(screen.getByRole('button', { name: 'Save tax settings' }));
    expect(
      await screen.findByText('Choose an installed provider and tax year'),
    ).toBeVisible();

    await user.click(providerSelect);
    await user.click(screen.getByText(`${provider.display_name} — 2026`));
    await user.click(screen.getByText('Advanced'));
    const parameters = screen.getByLabelText('Provider settings as JSON');
    fireEvent.change(parameters, { target: { value: '{"resident":true}' } });
    await user.click(screen.getByRole('button', { name: 'Save tax settings' }));

    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody).toMatchObject({
      jurisdiction: 'NZ',
      settings: {
        calculation_mode: 'AUTOMATIC',
        parameters: { resident: true },
      },
      tax_year: '2026',
    });
    expect(await screen.findByText('Tax settings saved')).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(screen.getByRole('table', { name: 'Tax settings' })).toBeVisible();
  });

  it('keeps manual net income usable when provider discovery fails', async () => {
    const user = userEvent.setup();
    let requestBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/tax-providers'))
          return Promise.resolve(
            response({ detail: 'Provider catalogue unavailable' }, 500),
          );
        if (path.endsWith('/tax-profiles') && init?.method === 'POST') {
          if (typeof init.body !== 'string')
            throw new Error('Expected a JSON request body');
          requestBody = JSON.parse(init.body) as Record<string, unknown>;
          return Promise.resolve(
            response(
              {
                ...automaticProfile,
                jurisdiction: 'CA',
                settings: {
                  calculation_mode: 'MANUAL_NET',
                  manual_annual_net_income: '60000',
                  parameters: {},
                },
              },
              201,
            ),
          );
        }
        if (path.endsWith('/tax-profiles'))
          return Promise.resolve(response([]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );

    renderPanel();
    expect(
      await screen.findByText(/Installed tax providers could not be loaded/i),
    ).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Add tax settings' }));
    await user.click(screen.getByLabelText('Calculation method'));
    await user.click(screen.getByText('Manual annual net income'));
    await user.type(screen.getByLabelText('Jurisdiction'), 'ca');
    await user.type(screen.getByLabelText('Tax year'), '2026');
    await user.type(screen.getByLabelText('Annual net income'), '60000');
    await user.click(screen.getByRole('button', { name: 'Save tax settings' }));

    await waitFor(() => expect(requestBody).toBeDefined());
    expect(requestBody).toMatchObject({
      jurisdiction: 'CA',
      settings: {
        calculation_mode: 'MANUAL_NET',
        manual_annual_net_income: '60000',
      },
      tax_year: '2026',
    });
  });
});

const validProfile = {
  effectiveFrom: '2026-08-02',
  effectiveTo: '',
  manualAnnualNetIncome: '',
  manualJurisdiction: '',
  manualTaxYear: '',
  mode: 'AUTOMATIC',
  parameters: '{}',
  providerYear: 'NZ|2026',
} as const;

describe('tax profile validation', () => {
  it.each(['[]', 'null', '{broken'])(
    'rejects non-object provider JSON %s',
    (parameters) => {
      expect(
        taxProfileSchema.safeParse({ ...validProfile, parameters }).success,
      ).toBe(false);
    },
  );

  it('requires all manual net-income fields', () => {
    expect(
      taxProfileSchema.safeParse({
        ...validProfile,
        mode: 'MANUAL_NET',
        providerYear: '',
      }).success,
    ).toBe(false);
  });
});
