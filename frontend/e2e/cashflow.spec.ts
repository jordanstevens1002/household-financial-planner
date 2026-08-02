import { expect, test } from '@playwright/test';

test('records a dated household expense', async ({ page }) => {
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
  await page.getByRole('button', { name: 'Add expense' }).click();
  await page.getByLabel('Expense name').fill('Electricity');
  await page.getByLabel('Category').click();
  await page.getByText('Utilities').click();
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
