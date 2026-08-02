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
