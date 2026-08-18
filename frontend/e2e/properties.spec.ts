import { expect, test } from '@playwright/test';

test('selects and restores a dated property position', async ({ page }) => {
  test.setTimeout(60_000);
  const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
  const propertyId = '818badb5-2518-4c3f-8f6d-bb6ee750e606';
  const typeId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';
  const statusId = '85e30193-a324-4d22-9065-e25d819f6530';
  const loanTypeId = 'b7efb821-85ea-45c6-a4af-bde69c898d87';
  const requestedDates: string[] = [];
  let valuationAdded = false;
  let valuationPayload: Record<string, unknown> | null = null;
  let ownershipPayload: Record<string, unknown> | null = null;
  let rentalPayload: Record<string, unknown> | null = null;
  let expensePayload: Record<string, unknown> | null = null;
  let loanPayload: Record<string, unknown> | null = null;
  let wizardPayload: Record<string, unknown> | null = null;
  await page.addInitScript((id) => {
    localStorage.setItem('hfp.selection.household', id);
  }, householdId);
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith('/auth/session')) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
          account: {
            display_name: 'Browser Owner',
            email: null,
            global_role: 'USER',
            id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
            must_change_password: false,
            username: 'property-owner',
          },
        },
      });
      return;
    }
    if (path.endsWith('/households')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            currency: 'NZD',
            display_name: 'Browser household',
            id: householdId,
            jurisdiction: 'NZ',
          },
        ],
      });
      return;
    }
    if (path.endsWith(`/households/${householdId}/access`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: { can_edit: true, can_manage: true, role: 'OWNER' },
      });
      return;
    }
    if (path.endsWith('/reference/countries')) {
      await route.fulfill({ contentType: 'application/json', json: [] });
      return;
    }
    if (path.endsWith('/properties/wizard') && request.method() === 'POST') {
      wizardPayload = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        contentType: 'application/json',
        json: {
          baseline: {
            baseline_date: '2026-08-02',
            id: '7023926d-f832-4190-94b6-6464df29dac2',
            loan_balance_total: '250000.00',
            notes: null,
            property_id: propertyId,
            property_value: '810000.00',
            status_id: statusId,
          },
          ownership: [],
          property: {
            address_line_1: null,
            address_line_2: null,
            country_code: null,
            current_status_id: statusId,
            default_currency: 'NZD',
            display_name: 'New current home',
            household_id: householdId,
            id: propertyId,
            notes: null,
            postal_code: null,
            property_type_id: typeId,
            purchase_date: null,
            purchase_price: null,
            sale_date: null,
            state_or_region: null,
            suburb_or_locality: null,
          },
          valuation: null,
          warnings: [],
        },
        status: 201,
      });
      return;
    }
    if (path.endsWith('/property-summaries')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            currency: 'NZD',
            current_status_id: statusId,
            current_value: '780000.00',
            display_name: 'Browser home',
            id: propertyId,
            position_date: '2026-06-30',
            property_type_id: typeId,
            purchase_date: '2020-02-01',
            purchase_price: '520000.00',
            setup_mode: 'CURRENT_SNAPSHOT',
            total_property_debt: '310000.00',
          },
        ],
      });
      return;
    }
    if (path.endsWith('/lookups/property_type')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          { id: typeId, code: 'HOUSE', display_name: 'House', is_active: true },
        ],
      });
      return;
    }
    if (path.endsWith('/lookups/property_status')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          { id: statusId, code: 'HOME', display_name: 'Home', is_active: true },
        ],
      });
      return;
    }
    if (path.endsWith('/lookups/property_expense_type')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            code: 'INSURANCE',
            display_name: 'Insurance',
            id: '487288b5-9cf2-4760-b903-dce0e5c09627',
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path.endsWith('/lookups/loan_type')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            code: 'HOME_LOAN',
            display_name: 'Home loan',
            id: loanTypeId,
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path.endsWith(`/households/${householdId}/loans`)) {
      if (request.method() === 'POST') {
        loanPayload = request.postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          contentType: 'application/json',
          json: {
            ...loanPayload,
            id: '7a959699-d6a5-4b32-a15f-cbe2a460ce55',
          },
          status: 201,
        });
      } else {
        await route.fulfill({
          contentType: 'application/json',
          json: loanPayload
            ? [
                {
                  ...loanPayload,
                  id: '7a959699-d6a5-4b32-a15f-cbe2a460ce55',
                },
              ]
            : [],
        });
      }
      return;
    }
    if (path.endsWith(`/properties/${propertyId}`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
          address_line_1: '4 Example Street',
          address_line_2: null,
          country_code: 'NZ',
          current_status_id: statusId,
          default_currency: 'NZD',
          display_name: 'Browser home',
          household_id: householdId,
          id: propertyId,
          notes: null,
          postal_code: '6011',
          property_type_id: typeId,
          purchase_date: '2020-02-01',
          purchase_price: '520000.00',
          sale_date: null,
          state_or_region: 'Wellington',
          suburb_or_locality: 'Island Bay',
        },
      });
      return;
    }
    if (
      path.endsWith(`/properties/${propertyId}/valuations`) &&
      request.method() === 'POST'
    ) {
      valuationPayload = request.postDataJSON() as Record<string, unknown>;
      valuationAdded = true;
      await route.fulfill({
        contentType: 'application/json',
        json: {
          id: '00d8bb19-b984-47f6-95e4-f804585803ff',
          is_estimate: false,
          notes: null,
          property_id: propertyId,
          source: 'Independent valuer',
          valuation_date: '2026-07-15',
          valuation_type: 'FORMAL_VALUATION',
          value: '805000.00',
        },
        status: 201,
      });
      return;
    }
    if (path.endsWith(`/properties/${propertyId}/state`)) {
      requestedDates.push(url.searchParams.get('as_of') ?? '');
      const asOf = url.searchParams.get('as_of') ?? '2026-08-02';
      await route.fulfill({
        contentType: 'application/json',
        json: {
          applied_event_ids: [],
          as_of: asOf,
          baseline_date: '2026-06-30',
          baseline_id: '7023926d-f832-4190-94b6-6464df29dac2',
          data_quality_flags: [],
          is_active_asset: true,
          loan_balance_total: '305000.00',
          property_id: propertyId,
          property_value: valuationAdded ? '805000.00' : '790000.00',
          status_id: statusId,
          temporal_position: 'CURRENT',
          valuation_date: valuationAdded ? '2026-07-15' : null,
          valuation_id: valuationAdded
            ? '00d8bb19-b984-47f6-95e4-f804585803ff'
            : null,
          valuation_is_estimate: valuationAdded ? false : null,
          valuation_type: valuationAdded ? 'FORMAL_VALUATION' : null,
        },
      });
      return;
    }
    if (path.endsWith(`/households/${householdId}/people`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            display_name: 'Alex',
            effective_from: '2020-01-01',
            id: '8a76ff72-b719-4ca9-9f77-b66f901fb56f',
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path.endsWith(`/properties/${propertyId}/ownership-position`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
          as_of: url.searchParams.get('as_of'),
          ownership: [],
          total_percentage: ownershipPayload ? '60.00' : '0.00',
          warnings: [
            `Ownership totals ${ownershipPayload ? '60.00' : '0.00'}% rather than 100.00% for the effective date`,
          ],
        },
      });
      return;
    }
    if (path.endsWith(`/properties/${propertyId}/ownership`)) {
      if (request.method() === 'POST') {
        ownershipPayload = request.postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          contentType: 'application/json',
          json: {
            ownership: {
              ...ownershipPayload,
              id: 'f263fb67-ff9f-4469-8d81-b89f07146624',
              property_id: propertyId,
            },
            total_percentage: '60.00',
            warnings: [
              'Ownership totals 60.00% rather than 100.00% for the effective date',
            ],
          },
          status: 201,
        });
      } else {
        await route.fulfill({ contentType: 'application/json', json: [] });
      }
      return;
    }
    if (path.endsWith(`/properties/${propertyId}/rental-profiles`)) {
      if (request.method() === 'POST') {
        rentalPayload = request.postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          contentType: 'application/json',
          json: {
            ...rentalPayload,
            id: 'a57994c3-76a7-475f-ae76-bf17228f04b4',
            property_id: propertyId,
          },
          status: 201,
        });
      } else {
        await route.fulfill({ contentType: 'application/json', json: [] });
      }
      return;
    }
    if (path.endsWith(`/properties/${propertyId}/expenses`)) {
      if (request.method() === 'POST') {
        expensePayload = request.postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          contentType: 'application/json',
          json: {
            ...expensePayload,
            id: '70534b12-fb69-41a2-9700-31f1c3123bd8',
            property_id: propertyId,
          },
          status: 201,
        });
      } else {
        await route.fulfill({ contentType: 'application/json', json: [] });
      }
      return;
    }
    if (path.endsWith(`/properties/${propertyId}/cashflow`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
          charged_rent_equivalent: '18200.00',
          currency: 'NZD',
          from_date: url.searchParams.get('from_date'),
          gross_rent: '18200.00',
          letting_fees: '0.00',
          management_fee: '1324.05',
          market_rent_equivalent: '20800.00',
          net_cashflow: '15129.95',
          property_expenses: '1200.00',
          property_id: propertyId,
          rent_difference: '-2600.00',
          rental_days: 365,
          to_date: url.searchParams.get('to_date'),
          vacancy_cost: '546.00',
          warnings: ['Recurring amounts use a 365-day planning year'],
        },
      });
      return;
    }
    await route.abort();
  });

  await page.goto('/properties');
  const table = page.getByRole('table', { name: 'Household properties' });
  await expect(table).toContainText('NZ$520,000.00');
  await expect(table).toContainText('NZ$780,000.00');
  await expect(table).toContainText('NZ$310,000.00');
  await page.getByRole('button', { name: 'View' }).click();
  await expect(
    page.getByText('4 Example Street, Island Bay, Wellington, 6011, NZ'),
  ).toBeVisible();
  await expect(page.getByText('NZ$790,000.00')).toBeVisible();
  await expect(page.getByText('NZ$305,000.00')).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem('hfp.selection.property')),
    )
    .toBe(propertyId);

  await page.getByRole('button', { name: 'Review loans' }).click();
  await expect(page.getByText('No property loans')).toBeVisible();
  await page.getByRole('button', { name: 'Add loan' }).click();
  const loanDialog = page.getByRole('dialog', { name: 'Add a property loan' });
  await loanDialog.getByLabel('Loan name').fill('Main mortgage');
  await loanDialog.getByLabel('Loan type').click();
  await page.getByRole('option', { name: 'Home loan' }).click();
  await loanDialog.getByLabel('Opening balance (NZD)').fill('305000');
  await loanDialog.getByLabel('Opening balance date').fill('2026-06-30');
  await loanDialog.getByLabel('Annual interest rate %').fill('5.75');
  await loanDialog.getByLabel('Scheduled repayment (NZD)').fill('2200');
  await loanDialog.getByLabel('Repayment frequency').click();
  await page.getByRole('option', { name: 'Monthly' }).click();
  await loanDialog.getByLabel('Repayment type').click();
  await page.getByRole('option', { name: 'Principal and interest' }).click();
  await loanDialog.getByLabel('Interest calculation').click();
  await page.getByRole('option', { name: 'Daily' }).click();
  await loanDialog.getByRole('button', { name: 'Save loan' }).click();
  await expect(page.getByText('Loan added')).toBeVisible();
  await expect(
    page.getByRole('table', { name: 'Property loans' }),
  ).toContainText('Main mortgage');
  await expect
    .poll(() => loanPayload)
    .toMatchObject({
      currency: 'NZD',
      initial_interest_rate: '5.75',
      loan_type_id: loanTypeId,
      opening_balance: '305000',
      property_id: propertyId,
      repayment_frequency: 'MONTHLY',
      scheduled_repayment: '2200',
    });

  await page.reload();
  await expect(page.getByRole('button', { name: 'Selected' })).toBeVisible();
  await page.getByLabel('Position date').fill('2028-07-01');
  await expect(page.getByText(/position date has changed/i)).toBeVisible();
  await page.getByRole('button', { name: 'Refresh position' }).click();
  await expect.poll(() => requestedDates).toContain('2028-07-01');
  await expect(page.getByText(/Results as of 2028-07-01/)).toBeVisible();

  await page.getByRole('button', { name: 'Add dated record' }).click();
  await page.getByLabel('Record date').fill('2026-07-15');
  await page.getByLabel('Property value (NZD)').fill('805000');
  await page.getByLabel('Valuation type').click();
  await page.getByRole('option', { name: 'Formal valuation' }).click();
  await expect(
    page.getByText('A formal valuation is recorded as a non-estimate.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Advanced' }).click();
  await page.getByLabel('Source (optional)').fill('Independent valuer');
  await page.getByRole('button', { name: 'Save record' }).click();
  await expect(
    page.getByText('Valuation recorded', { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => valuationPayload)
    .toEqual({
      is_estimate: false,
      notes: null,
      source: 'Independent valuer',
      valuation_date: '2026-07-15',
      valuation_type: 'FORMAL_VALUATION',
      value: '805000',
    });
  await expect(page.getByText('Valuation recorded Jul 15, 2026')).toBeVisible();

  await page.getByRole('button', { name: 'Add ownership record' }).click();
  const ownershipDialog = page.getByRole('dialog', {
    name: 'Add ownership record',
  });
  await ownershipDialog.getByLabel('Owner', { exact: true }).click();
  await page
    .getByRole('option', { name: 'A person in this household' })
    .click();
  await ownershipDialog.getByLabel('Person', { exact: true }).click();
  await page.getByRole('option', { name: 'Alex' }).click();
  await ownershipDialog.getByLabel('Ownership percentage').fill('60');
  await ownershipDialog.getByLabel('Effective from').fill('2020-02-01');
  await ownershipDialog.getByRole('button', { name: 'Save ownership' }).click();
  await expect(
    page.getByText(/Ownership saved\. Ownership totals 60\.00%/),
  ).toBeVisible();
  await expect
    .poll(() => ownershipPayload)
    .toMatchObject({
      effective_from: '2020-02-01',
      owner_type: 'PERSON',
      ownership_percentage: '60',
      person_id: '8a76ff72-b719-4ca9-9f77-b66f901fb56f',
    });

  await page.getByRole('button', { name: 'Add rental arrangement' }).click();
  const rentalDialog = page.getByRole('dialog', {
    name: 'Add rental arrangement',
  });
  await rentalDialog.getByLabel('Rental scope').click();
  await page.getByRole('option', { name: 'Part of the property' }).click();
  await rentalDialog.getByLabel('Rental area name').fill('Granny flat');
  await rentalDialog.getByLabel('Property share (%)').fill('30');
  await rentalDialog
    .getByLabel('Rent charged for this arrangement (NZD)')
    .fill('350');
  await rentalDialog.getByLabel('Effective from').fill('2026-09-01');
  await rentalDialog
    .getByRole('button', { name: 'Save rental arrangement' })
    .click();
  await expect(page.getByText('Rental arrangement saved')).toBeVisible();
  await expect
    .poll(() => rentalPayload)
    .toMatchObject({
      charged_rent_amount: '350',
      display_name: 'Granny flat',
      effective_from: '2026-09-01',
      frequency: 'WEEKLY',
      rental_share_percentage: '30',
    });

  await page.getByRole('button', { name: 'Review rental finances' }).click();
  await expect(page.getByText('NZ$15,129.95')).toBeVisible();
  await page.getByRole('button', { name: 'Add property expense' }).click();
  const expenseDialog = page.getByRole('dialog', {
    name: 'Add property expense',
  });
  await expenseDialog.getByLabel('Expense name').fill('Building insurance');
  await expenseDialog.getByLabel('Expense type').click();
  await page.getByRole('option', { name: 'Insurance' }).click();
  await expenseDialog.getByLabel('Amount (NZD)').fill('1200');
  await expenseDialog.getByLabel('Effective from').fill('2026-01-01');
  await expenseDialog.getByRole('button', { name: 'Save expense' }).click();
  await expect(page.getByText('Property expense added')).toBeVisible();
  await expect
    .poll(() => expensePayload)
    .toMatchObject({
      amount: '1200',
      display_name: 'Building insurance',
      expense_type_id: '487288b5-9cf2-4760-b903-dce0e5c09627',
      is_rental_expense: false,
    });

  await page.getByRole('button', { name: 'Add property', exact: true }).click();
  await page.getByLabel('Property name').fill('New current home');
  await page.getByLabel('Property type').click();
  await page.getByRole('option', { name: 'House' }).click();
  await page.getByLabel('Current use').click();
  await page.getByRole('option', { name: 'Home' }).click();
  await page.getByLabel('Property value (NZD)').fill('810000');
  await page.getByLabel('Total property debt (NZD)').fill('250000');
  await page.getByRole('button', { name: 'Save property' }).click();
  await expect(page.getByText('Property added')).toBeVisible();
  await expect
    .poll(() => wizardPayload)
    .toMatchObject({
      baseline: {
        loan_balance_total: '250000',
        property_value: '810000',
        status_id: statusId,
      },
      mode: 'CURRENT_SNAPSHOT',
      property: {
        display_name: 'New current home',
        purchase_date: null,
        purchase_price: null,
      },
    });
});
