import { expect, test } from '@playwright/test';

test('creates and lists a purchase plan', async ({ page }) => {
  const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
  const purchaseTypeId = '16b3f01b-ff76-451f-a4bd-a2ddf89834fd';
  let plans: Record<string, unknown>[] = [];
  await page.addInitScript((id) => {
    localStorage.setItem('hfp.selection.household', id);
  }, householdId);
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/auth/session')) {
      await route.fulfill({
        json: {
          account: {
            display_name: 'Browser Editor',
            email: null,
            global_role: 'USER',
            id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
            must_change_password: false,
            username: 'purchase-editor',
          },
        },
      });
      return;
    }
    if (path.endsWith('/households')) {
      await route.fulfill({
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
    if (path.endsWith('/lookups/purchase_type')) {
      await route.fulfill({
        json: [
          {
            category: 'purchase_type',
            code: 'HOME',
            display_name: 'Established home',
            id: purchaseTypeId,
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path.endsWith('/purchase-providers')) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith('/people')) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith('/calculate') && request.method() === 'POST') {
      await route.fulfill({
        json: {
          additional_loan_required: '650000.00',
          assumptions_used: ['Manual plan without a purchase-cost provider.'],
          available_equity_funding: '50000.00',
          calculation_date: '2026-10-08',
          costs: [],
          currency: 'NZD',
          existing_borrowed_funding: '0.00',
          failed_thresholds: [],
          funding_gap: '0.00',
          is_feasible: true,
          is_within_target_price_range: true,
          lvr: '92.8571',
          monthly_loan_repayment: '3896.00',
          projected_monthly_surplus: '1104.00',
          purchase_plan_id: plans[0]?.id,
          purchase_price: '700000.00',
          required_total: '700000.00',
          total_debt_funding: '650000.00',
          warnings: [],
        },
      });
      return;
    }
    if (path.match(/\/purchase-plans\/[0-9a-f-]+$/)) {
      await route.fulfill({
        json: {
          ...plans[0],
          costs: [],
          funding_sources: [],
          ownership: [],
        },
      });
      return;
    }
    if (path.endsWith('/purchase-plans') && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>;
      plans = [
        {
          ...body,
          household_id: householdId,
          id: '6ace21c6-058c-4f42-af75-d2eb55da6077',
        },
      ];
      await route.fulfill({ json: plans[0], status: 201 });
      return;
    }
    if (path.endsWith('/purchase-plans')) {
      await route.fulfill({ json: plans });
      return;
    }
    await route.abort();
  });

  await page.goto('/purchase-plans');
  await page.getByRole('button', { name: 'Add purchase plan' }).click();
  const dialog = page.getByRole('dialog', { name: 'Add purchase plan' });
  await dialog.getByRole('textbox', { name: /Plan name/ }).fill('Future home');
  await dialog.getByRole('combobox', { name: /Purchase type/ }).click();
  await page.getByRole('option', { name: 'Established home' }).click();
  await dialog.getByLabel('Minimum price (NZD)').fill('700000');
  await dialog.getByLabel('Maximum price (NZD)').fill('850000');
  await dialog.getByRole('button', { name: 'Save plan' }).click();

  await expect(page.getByText('Purchase plan saved.')).toBeVisible();
  await expect(
    page.getByRole('table', { name: 'Purchase plans' }),
  ).toContainText('Future home');
  expect(plans[0]).toMatchObject({
    currency: 'NZD',
    provider_code: null,
    purchase_type_id: purchaseTypeId,
  });

  await page.getByRole('button', { name: 'View details' }).click();
  const details = page.getByRole('dialog', { name: 'Future home' });
  await expect(details).toContainText('No funding sources recorded.');
  await expect(details).toContainText('No user-entered costs recorded.');
  await expect(details).toContainText('No proposed ownership recorded.');
  await details.getByLabel('Maximum additional borrowing (NZD)').fill('650000');
  await details.getByLabel('Current monthly surplus (NZD)').fill('5000');
  await details.getByRole('button', { name: 'Calculate' }).click();
  await expect(details).toContainText(
    'This plan satisfies the saved comfort thresholds.',
  );
  await expect(details).toContainText('No purchase costs were included.');
});
