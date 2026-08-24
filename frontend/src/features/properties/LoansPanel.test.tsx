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
import { NotificationProvider } from '../../shared/NotificationProvider';
import { LoansPanel } from './LoansPanel';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ csrfToken: () => 'csrf-token' }),
}));

const householdId = '1bfbb15e-5293-4e29-95e0-f86b82e62528';
const propertyId = '818badb5-2518-4c3f-8f6d-bb6ee750e606';
const otherPropertyId = '19528fd9-ad60-4621-b41a-012f21a98e2e';
const loanTypeId = '951bd6cd-82db-4a37-a56f-95c36b02f9d1';
const groupId = '47cf84d0-3151-4b75-9667-e5daa7e822d9';

function response(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
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

function loan(
  id = '997d68f7-bf03-4f70-97bb-80cfe8619d09',
  property = propertyId,
) {
  const record = {
    account_reference_masked: null,
    currency: 'NZD',
    display_name: 'Home loan',
    household_id: householdId,
    id,
    initial_interest_rate: '5.7500',
    interest_calculation_method: 'DAILY',
    is_active: true,
    is_interest_only: false,
    lender: 'Example lender',
    loan_group_id: null,
    loan_type_id: loanTypeId,
    notes: null,
    opening_balance: '310000.00',
    opening_balance_date: '2026-06-30',
    original_balance: null,
    property_id: property,
    repayment_frequency: 'MONTHLY',
    scheduled_repayment: '2100.00',
    term_months: 360,
  };
  return record as Omit<typeof record, 'loan_group_id'> & {
    loan_group_id: string | null;
  };
}

function group(
  id = groupId,
  displayName = 'Fixed splits',
  property = propertyId,
) {
  return {
    display_name: displayName,
    household_id: householdId,
    id,
    property_id: property,
  };
}

function renderPanel(
  canEdit = true,
  recordedDebt: string | null = '310000.00',
) {
  return render(
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
      <NotificationProvider>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <LoansPanel
            canEdit={canEdit}
            currency="NZD"
            householdId={householdId}
            propertyId={propertyId}
            recordedDebt={recordedDebt}
            recordedDebtDate="2026-06-30"
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

describe('property loan records', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('lists only the selected property loans for a viewer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(
            response([
              {
                code: 'VARIABLE_RATE',
                display_name: 'Variable rate',
                id: loanTypeId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(
            response([
              loan(),
              loan('17223c91-b956-4f70-8431-01fe4a140eb8', otherPropertyId),
            ]),
          );
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel(false);

    const table = await screen.findByRole('table', { name: 'Property loans' });
    expect(table).toHaveTextContent('Home loan');
    expect(table).toHaveTextContent('Variable rate');
    expect(table).toHaveTextContent('NZ$310,000.00');
    expect(
      screen.getByText(
        /Active linked-loan opening balances total NZD 310,000\.00/,
      ),
    ).toBeVisible();
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Add loan' })).toBeNull();
    expect(
      screen.queryByRole('button', { name: 'Add split group' }),
    ).toBeNull();
  });

  it('validates material fields and creates a property-linked loan', async () => {
    let saved: Record<string, unknown> | null = null;
    let loans: unknown[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(
            response([
              {
                code: 'VARIABLE_RATE',
                display_name: 'Variable rate',
                id: loanTypeId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`)) {
          if (init?.method === 'POST') {
            saved = JSON.parse(init.body as string) as Record<string, unknown>;
            loans = [loan()];
            return Promise.resolve(response(loan(), 201));
          }
          return Promise.resolve(response(loans));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole('button', { name: 'Add loan' }));
    await user.click(screen.getByRole('button', { name: 'Save loan' }));
    expect(await screen.findByText('Enter a loan name')).toBeVisible();
    expect(screen.getByText('Choose a loan type')).toBeVisible();

    await user.type(screen.getByLabelText('Loan name'), 'Home loan');
    await choose('Loan type', 'Variable rate');
    await user.type(screen.getByLabelText('Opening balance (NZD)'), '310000');
    fireEvent.change(screen.getByLabelText('Opening balance date'), {
      target: { value: '2026-06-30' },
    });
    await user.type(screen.getByLabelText('Annual interest rate %'), '5.75');
    await user.type(screen.getByLabelText('Scheduled repayment (NZD)'), '2100');
    await choose('Repayment frequency', 'Monthly');
    await user.type(screen.getByLabelText('Term in months'), '360');
    await choose('Repayment type', 'Principal and interest');
    await choose('Interest calculation', 'Daily');
    await user.click(screen.getByRole('button', { name: 'Save loan' }));

    expect(await screen.findByText('Loan added')).toBeVisible();
    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved).toMatchObject({
      currency: 'NZD',
      initial_interest_rate: '5.75',
      interest_calculation_method: 'DAILY',
      is_interest_only: false,
      loan_type_id: loanTypeId,
      opening_balance: '310000',
      opening_balance_date: '2026-06-30',
      property_id: propertyId,
      repayment_frequency: 'MONTHLY',
      scheduled_repayment: '2100',
      term_months: 360,
    });
    expect(
      await screen.findByRole('table', { name: 'Property loans' }),
    ).toHaveTextContent('Home loan');
  }, 30_000);

  it('shows a recoverable loan-list failure', async () => {
    let failed = true;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`)) {
          if (failed) {
            failed = false;
            return Promise.resolve(
              response({ detail: 'Temporary outage' }, 503),
            );
          }
          return Promise.resolve(response([]));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();
    expect(
      await screen.findByText(/Property loans could not be loaded/),
    ).toBeVisible();
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('No property loans')).toBeVisible();
  });

  it('shows a recoverable split-group catalogue failure', async () => {
    let failed = true;
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loan-groups`)) {
          if (failed) {
            failed = false;
            return Promise.resolve(response({ detail: 'Unavailable' }, 503));
          }
          return Promise.resolve(response([]));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();
    expect(
      await screen.findByText(/Loan split groups could not be loaded/),
    ).toBeVisible();
    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() =>
      expect(
        screen.queryByText(/Loan split groups could not be loaded/),
      ).toBeNull(),
    );
  });

  it('keeps mixed-currency group totals separate and decimal-exact', async () => {
    const large = '9999999999999999.99';
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response([group()]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(
            response([
              {
                ...loan(),
                currency: 'AUD',
                loan_group_id: groupId,
                opening_balance: large,
              },
              {
                ...loan('17223c91-b956-4f70-8431-01fe4a140eb8'),
                currency: 'AUD',
                loan_group_id: groupId,
                opening_balance: large,
              },
              {
                ...loan('46aa75ae-929b-4d92-bca8-bf578c32e8b2'),
                currency: 'NZD',
                loan_group_id: groupId,
                opening_balance: '1.01',
              },
            ]),
          );
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();
    expect(
      await within(
        await screen.findByLabelText('Loan split groups'),
      ).findByText(/AUD 19,999,999,999,999,999\.98; NZD 1\.01/),
    ).toBeVisible();
  });

  it('distinguishes loading, failed and unknown split-group assignments', async () => {
    let resolveGroups: ((value: Response) => void) | undefined;
    const pendingGroups = new Promise<Response>((resolve) => {
      resolveGroups = resolve;
    });
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(
            response([{ ...loan(), loan_group_id: groupId }]),
          );
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return pendingGroups;
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();
    const table = await screen.findByRole('table', { name: 'Property loans' });
    expect(within(table).getByText('Loading…')).toBeVisible();
    resolveGroups?.(response([]));
    expect(
      await within(table).findByText('Invalid group assignment'),
    ).toBeVisible();
  });

  it('marks a grouped loan unavailable when its catalogue request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(
            response([{ ...loan(), loan_group_id: groupId }]),
          );
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response({ detail: 'Unavailable' }, 503));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    renderPanel();
    expect(await screen.findByText('Group unavailable')).toBeVisible();
    expect(screen.queryByText('Ungrouped')).toBeNull();
  });

  it('corrects and closes a loan while explaining conflicting recorded debt', async () => {
    let current = loan();
    const patches: Record<string, unknown>[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(
            response([
              {
                code: 'VARIABLE_RATE',
                display_name: 'Variable rate',
                id: loanTypeId,
                is_active: true,
              },
            ]),
          );
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(response([current]));
        if (path.endsWith(`/loans/${current.id}`) && init?.method === 'PATCH') {
          const patch = JSON.parse(init.body as string) as Record<
            string,
            unknown
          >;
          patches.push(patch);
          current = { ...current, ...patch };
          return Promise.resolve(response(current));
        }
        if (
          path.endsWith(`/loans/${current.id}/close`) &&
          init?.method === 'POST'
        ) {
          const close = JSON.parse(init.body as string) as Record<
            string,
            unknown
          >;
          patches.push(close);
          current = { ...current, is_active: false };
          return Promise.resolve(response(current));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel(true, '250000.00');
    expect(
      await screen.findByText(/Recorded property debt.*NZ\$250,000\.00/),
    ).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Correct' }));
    const correction = screen.getByRole('dialog', {
      name: 'Correct property loan',
    });
    await user.clear(
      within(correction).getByLabelText('Scheduled repayment (NZD)'),
    );
    await user.type(
      within(correction).getByLabelText('Scheduled repayment (NZD)'),
      '2250',
    );
    await user.click(
      within(correction).getByRole('button', { name: 'Save correction' }),
    );
    expect(await screen.findByText('Loan corrected')).toBeVisible();
    expect(patches[0]).toMatchObject({ scheduled_repayment: '2250' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    await user.click(
      within(screen.getByRole('table', { name: 'Property loans' })).getByRole(
        'button',
        { name: 'Close' },
      ),
    );
    await user.click(screen.getByRole('button', { name: 'Close loan' }));
    expect(await screen.findByText('Loan closed')).toBeVisible();
    const effectiveDate = patches[1]?.effective_date;
    expect(typeof effectiveDate).toBe('string');
    expect(effectiveDate as string).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(await screen.findByText('Closed')).toBeVisible();
  }, 15_000);

  it('rejects an exposed account reference and explains missing recorded debt', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loan-groups`))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(response([loan()]));
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel(true, null);
    expect(await screen.findByText(/is not available/)).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Correct' }));
    await user.click(screen.getByRole('button', { name: 'Advanced' }));
    const reference = screen.getByLabelText(
      'Masked account reference (optional)',
    );
    await user.type(reference, '123456789');
    await user.click(screen.getByRole('button', { name: 'Save correction' }));
    expect(
      await screen.findByText(/Hide all but the final 2 to 4 characters/),
    ).toBeVisible();
  });

  it('creates, presents, assigns, renames and removes split groups', async () => {
    const emptyGroupId = 'a7e1ef72-7894-41d6-9303-22aa98c108f6';
    let groups = [group(), group(emptyGroupId, 'Offset split')];
    let currentLoans: ReturnType<typeof loan>[] = [
      { ...loan(), loan_group_id: groupId },
      loan('17223c91-b956-4f70-8431-01fe4a140eb8'),
    ];
    const writes: Array<{ method: string; path: string; body?: unknown }> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>((input, init) => {
        const path = pathOf(input);
        if (path.endsWith('/lookups/loan_type'))
          return Promise.resolve(response([]));
        if (path.endsWith(`/households/${householdId}/loans`))
          return Promise.resolve(response(currentLoans));
        if (path.endsWith(`/households/${householdId}/loan-groups`)) {
          if (init?.method === 'POST') {
            const body = JSON.parse(init.body as string) as {
              display_name: string;
            };
            const created = group(
              'b20e35bc-2bfe-42b0-ad33-38e3507787ab',
              body.display_name,
            );
            groups = [...groups, created];
            writes.push({ body, method: 'POST', path });
            return Promise.resolve(response(created, 201));
          }
          return Promise.resolve(response(groups));
        }
        const editedLoan = currentLoans[1];
        if (!editedLoan) throw new Error('Expected an ungrouped loan');
        if (path.endsWith(`/loans/${editedLoan.id}`)) {
          const body = JSON.parse(init?.body as string) as Record<
            string,
            unknown
          >;
          const updated = { ...editedLoan, ...body };
          currentLoans = [currentLoans[0]!, updated];
          writes.push({ body, method: 'PATCH', path });
          return Promise.resolve(response(currentLoans[1]));
        }
        const matchedGroup = groups.find((item) =>
          path.endsWith(`/loan-groups/${item.id}`),
        );
        if (matchedGroup && init?.method === 'PATCH') {
          const body = JSON.parse(init.body as string) as {
            display_name: string;
          };
          groups = groups.map((item) =>
            item.id === matchedGroup.id
              ? { ...item, display_name: body.display_name }
              : item,
          );
          writes.push({ body, method: 'PATCH', path });
          return Promise.resolve(
            response({ ...matchedGroup, display_name: body.display_name }),
          );
        }
        if (matchedGroup && init?.method === 'DELETE') {
          groups = groups.filter((item) => item.id !== matchedGroup.id);
          writes.push({ method: 'DELETE', path });
          return Promise.resolve(response(null, 204));
        }
        throw new Error(`Unexpected request: ${path}`);
      }),
    );
    const user = userEvent.setup();
    renderPanel();

    const table = await screen.findByRole('table', { name: 'Property loans' });
    expect(within(table).getByText('Fixed splits')).toBeVisible();
    expect(within(table).getByText('Ungrouped')).toBeVisible();
    expect(
      screen.getByText(/derived opening balance NZD 310,000\.00/),
    ).toBeVisible();

    await user.click(screen.getByRole('button', { name: 'Add split group' }));
    await user.click(screen.getByRole('button', { name: 'Add group' }));
    expect(await screen.findByText('Enter a split group name')).toBeVisible();
    await user.type(
      screen.getByLabelText('Split group name'),
      'Variable split',
    );
    await user.click(screen.getByRole('button', { name: 'Add group' }));
    expect(await screen.findByText('Split group added')).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    await user.click(
      screen.getByRole('button', { name: 'Rename Offset split' }),
    );
    await user.clear(screen.getByLabelText('Split group name'));
    await user.type(
      screen.getByLabelText('Split group name'),
      'Offset facility',
    );
    await user.click(screen.getByRole('button', { name: 'Save name' }));
    expect(await screen.findByText('Split group renamed')).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    await user.click(
      screen.getByRole('button', { name: 'Remove Offset facility' }),
    );
    await user.click(screen.getByRole('button', { name: 'Remove group' }));
    expect(await screen.findByText('Split group removed')).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    const currentTable = screen.getByRole('table', { name: 'Property loans' });
    const secondRow = within(currentTable).getAllByRole('row')[2]!;
    await user.click(
      within(secondRow).getByRole('button', { name: 'Correct' }),
    );
    await choose('Split group (optional)', 'Fixed splits');
    await user.click(screen.getByRole('button', { name: 'Save correction' }));
    await waitFor(() =>
      expect(
        writes.some(
          (write) =>
            (write.body as Record<string, unknown> | undefined)
              ?.loan_group_id === groupId,
        ),
      ).toBe(true),
    );
  }, 30_000);
});
