import { expect, test } from '@playwright/test';

test('records a dated household expense', async ({ page }) => {
  test.setTimeout(60_000);
  const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
  const categoryId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';
  let created: Record<string, unknown> | undefined;
  await page.addInitScript(
    ({ key, value }) => localStorage.setItem(key, value),
    { key: 'hfp.selection.household', value: householdId },
  );
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/auth/session')) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
          account: {
            display_name: 'Browser Editor',
            email: null,
            global_role: 'USER',
            id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
            must_change_password: false,
            username: 'cashflow-editor',
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
    if (path.endsWith('/access')) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
          can_administer: false,
          can_edit: true,
          can_manage_owners: false,
          can_view: true,
          role: 'EDITOR',
        },
      });
      return;
    }
    if (path.endsWith('/cashflow')) {
      await route.fulfill({
        contentType: 'application/json',
        json: {
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
              allocations: [],
              annual_repayment: '36000.00',
              currency: 'NZD',
              display_name: 'Browser home loan',
              included_in_household_total: true,
              loan_id: 'b9a6023d-6cc1-4ea8-b100-15fc9d488a0f',
              monthly_repayment: '3000.00',
              periodic_repayment: '1384.62',
              property_id: null,
              repayment_frequency: 'FORTNIGHTLY',
              warnings: [],
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
              display_name: 'Browser Person',
              gross_taxable_income: '100000.00',
              net_income: '80000.00',
              non_taxable_income: '0.00',
              person_id: '85e30193-a324-4d22-9065-e25d819f6530',
              tax_and_repayments: '20000.00',
              warnings: ['Latest installed tax rules used.'],
            },
          ],
          warnings: ['Latest installed tax rules used.'],
        },
      });
      return;
    }
    if (path.endsWith('/lookups/household_expense_type')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            category: 'household_expense_type',
            code: 'UTILITIES',
            display_name: 'Utilities',
            id: categoryId,
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path.endsWith('/people')) {
      await route.fulfill({ contentType: 'application/json', json: [] });
      return;
    }
    if (path.endsWith('/expenses') && request.method() === 'POST') {
      created = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        contentType: 'application/json',
        json: {
          ...created,
          household_id: householdId,
          id: '6ace21c6-058c-4f42-af75-d2eb55da6077',
        },
        status: 201,
      });
      return;
    }
    if (path.endsWith('/expenses')) {
      await route.fulfill({ contentType: 'application/json', json: [] });
      return;
    }
    await route.abort();
  });

  await page.goto('/cash-flow');
  await expect(page.getByText('Monthly surplus').locator('..')).toContainText(
    'NZ$3,166.67',
  );
  await expect(
    page.getByRole('table', { name: 'Person cash-flow projections' }),
  ).toContainText('AUTOMATIC');
  await expect(
    page.getByRole('table', { name: 'Automatic loan repayments' }),
  ).toContainText('Browser home loan');
  await page
    .getByRole('button', { name: 'Warnings for Browser Person' })
    .hover();
  await expect(
    page.getByText('Latest installed tax rules used.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Add expense' }).click();
  await page.getByLabel('Expense name').fill('Electricity');
  await page.getByLabel('Category').click();
  await page.getByRole('option', { name: 'Utilities' }).click();
  await page.getByLabel('Amount (NZD)').fill('210.75');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Add expense' })
    .click();

  await expect(page.getByText('Expense added')).toBeVisible();
  await expect(
    page.getByRole('table', { name: 'Household expenses' }),
  ).toContainText('Electricity');
  expect(created).toMatchObject({
    amount: '210.75',
    category_id: categoryId,
    display_name: 'Electricity',
    frequency: 'MONTHLY',
  });
});
