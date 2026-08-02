import { expect, test } from '@playwright/test';

const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const personId = '85e30193-a324-4d22-9065-e25d819f6530';
const incomeTypeId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';

test('creates and restores a selected person income source', async ({
  page,
}) => {
  const incomes: Record<string, unknown>[] = [];
  await page.addInitScript(
    ({ household, person }) => {
      localStorage.setItem('hfp.selection.household', household);
      localStorage.setItem('hfp.selection.person', person);
    },
    { household: householdId, person: personId },
  );
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: {
        account: {
          display_name: 'Browser Editor',
          email: null,
          global_role: 'USER',
          id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
          must_change_password: false,
          username: 'income-editor',
        },
      },
    }),
  );
  await page.route('**/api/v1/households', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: [
        {
          currency: 'NZD',
          display_name: 'Browser household',
          id: householdId,
          jurisdiction: 'NZ',
        },
      ],
    }),
  );
  await page.route('**/api/v1/households/*/people', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: [
        {
          date_of_birth: null,
          display_name: 'Browser Person',
          effective_from: '2026-08-02',
          effective_to: null,
          household_id: householdId,
          id: personId,
          is_active: true,
          legal_name: null,
          notes: null,
          tax_jurisdiction: null,
          tax_residency_country: 'NZ',
        },
      ],
    }),
  );
  await page.route('**/api/v1/households/*/access', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: {
        can_administer: false,
        can_edit: true,
        can_manage_owners: false,
        can_view: true,
        role: 'EDITOR',
      },
    }),
  );
  await page.route('**/api/v1/lookups/income_type', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: [
        {
          category: 'income_type',
          code: 'SALARY',
          display_name: 'Salary or wages',
          id: incomeTypeId,
          is_active: true,
        },
      ],
    }),
  );
  await page.route('**/api/v1/people/*/income-sources', async (route) => {
    if (route.request().method() === 'POST') {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      incomes.push({
        ...payload,
        id: '6ace21c6-058c-4f42-af75-d2eb55da6077',
        person_id: personId,
      });
      await route.fulfill({
        contentType: 'application/json',
        json: incomes[0],
        status: 201,
      });
      return;
    }
    await route.fulfill({ contentType: 'application/json', json: incomes });
  });

  await page.goto('/income');
  await expect(page.getByText('No income sources yet')).toBeVisible();
  await page.getByRole('button', { name: 'Add income source' }).first().click();
  await page.getByLabel('Income type').click();
  await page.getByText('Salary or wages').click();
  await page.getByLabel('Income name').fill('Primary salary');
  await page.getByLabel('Gross amount').fill('5000');
  await page.getByRole('button', { name: 'Add income source' }).click();

  await expect(
    page.getByRole('table', { name: 'Income sources' }),
  ).toContainText('Primary salary');
  expect(incomes[0]).toMatchObject({
    frequency: 'MONTHLY',
    gross_amount: '5000',
    income_type_id: incomeTypeId,
    taxable: true,
  });

  await page.reload();
  await expect(
    page.getByRole('table', { name: 'Income sources' }),
  ).toContainText('Primary salary');
});

test('calculates a provider tax estimate without saving household data', async ({
  page,
}) => {
  let calculation: Record<string, unknown> | undefined;
  await page.addInitScript(
    ({ household, person }) => {
      localStorage.setItem('hfp.selection.household', household);
      localStorage.setItem('hfp.selection.person', person);
    },
    { household: householdId, person: personId },
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
            username: 'income-editor',
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
    if (path.endsWith('/people')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            date_of_birth: null,
            display_name: 'Browser Person',
            effective_from: '2026-08-02',
            effective_to: null,
            household_id: householdId,
            id: personId,
            is_active: true,
            legal_name: null,
            notes: null,
            tax_jurisdiction: null,
            tax_residency_country: 'NZ',
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
    if (
      path.endsWith('/lookups/income_type') ||
      path.endsWith('/income-sources')
    ) {
      await route.fulfill({ contentType: 'application/json', json: [] });
      return;
    }
    if (path.endsWith('/tax-providers')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            display_name: 'Example New Zealand tax',
            jurisdiction: 'NZ',
            supported_tax_years: ['2026'],
          },
        ],
      });
      return;
    }
    if (path.endsWith('/reference/currencies')) {
      await route.fulfill({
        contentType: 'application/json',
        json: [
          {
            code: 'NZD',
            display_name: 'New Zealand Dollar',
            numeric_code: '554',
          },
        ],
      });
      return;
    }
    if (path.endsWith('/calculations/tax')) {
      calculation = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        contentType: 'application/json',
        json: {
          components: [
            {
              amount: '20000.00',
              code: 'income_tax',
              display_name: 'Income tax',
            },
          ],
          currency: 'NZD',
          jurisdiction: 'NZ',
          net_income: '80000.00',
          ruleset_version: 'NZ-2026-example',
          tax_year: '2026',
          taxable_income: '100000.00',
          total: '20000.00',
          warnings: ['Example provider warning'],
        },
      });
      return;
    }
    await route.abort();
  });

  await page.goto('/income');
  await page.getByRole('tab', { name: 'Tax estimate' }).click();
  await page.getByLabel('Currency').click();
  await page.getByText('NZD — New Zealand Dollar').click();
  await page.getByLabel('Gross taxable income').fill('100000');
  await page.getByLabel('Provider and tax year').click();
  await page.getByText('Example New Zealand tax — 2026').click();
  await page.getByRole('button', { name: 'Calculate estimate' }).click();

  await expect(page.getByLabel('Tax estimate result')).toContainText(
    'NZ-2026-example',
  );
  await expect(page.getByLabel('Tax estimate result')).toContainText(
    'Example provider warning',
  );
  expect(calculation).toMatchObject({
    currency: 'NZD',
    gross_taxable_income: '100000',
    jurisdiction: 'NZ',
    tax_year: '2026',
  });
});
