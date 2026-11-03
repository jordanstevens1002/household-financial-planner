import { expect, test } from '@playwright/test';

test('calculates a retirement projection with backend provenance', async ({
  page,
}) => {
  const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
  const accountId = '79fe9e91-0d62-4793-bdd2-c47befbf84ad';
  await page.addInitScript((id) => {
    localStorage.setItem('hfp.selection.household', id);
  }, householdId);
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/session')) {
      await route.fulfill({
        json: {
          account: {
            display_name: 'Browser Viewer',
            email: null,
            global_role: 'USER',
            id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
            must_change_password: false,
            username: 'retirement-viewer',
          },
        },
      });
      return;
    }
    if (path.endsWith('/households')) {
      await route.fulfill({
        json: [
          {
            currency: 'AUD',
            display_name: 'Browser household',
            id: householdId,
            jurisdiction: 'AU',
          },
        ],
      });
      return;
    }
    if (path.endsWith('/access')) {
      await route.fulfill({
        json: {
          can_administer: false,
          can_edit: false,
          can_manage_owners: false,
          can_view: true,
          role: 'VIEWER',
        },
      });
      return;
    }
    if (path.endsWith('/people')) {
      await route.fulfill({ json: [] });
      return;
    }
    if (path.endsWith('/lookups/retirement_account_type')) {
      await route.fulfill({
        json: [
          {
            category: 'retirement_account_type',
            code: 'AUSTRALIAN_SUPER',
            display_name: 'Australian superannuation',
            id: '16b3f01b-ff76-451f-a4bd-a2ddf89834fd',
            is_active: true,
          },
        ],
      });
      return;
    }
    if (path.endsWith('/retirement-providers')) {
      await route.fulfill({
        json: [
          {
            code: 'AU_SUPER',
            display_name: 'Australian superannuation',
            supported_account_type_codes: ['AUSTRALIAN_SUPER'],
          },
        ],
      });
      return;
    }
    if (path.endsWith('/retirement-accounts')) {
      await route.fulfill({
        json: [
          {
            account_type_id: '16b3f01b-ff76-451f-a4bd-a2ddf89834fd',
            annual_fees: '120.00',
            currency: 'AUD',
            display_name: 'Browser super',
            expected_return_rate: '6.0000',
            household_id: householdId,
            id: accountId,
            is_active: true,
            notes: null,
            opening_balance: '100000.00',
            opening_balance_date: '2026-01-01',
            person_id: null,
            provider_code: 'AU_SUPER',
            provider_settings: {},
            retirement_age: 67,
            revision: 1,
          },
        ],
      });
      return;
    }
    if (path.endsWith(`/${accountId}/projection`)) {
      await route.fulfill({
        json: {
          account_id: accountId,
          assumptions_used: ['Expected return is compounded monthly.'],
          calculation_date: '2026-11-03',
          currency: 'AUD',
          entries: [],
          projected_balance: '112000.00',
          projection_date: '2027-01-01',
          provider_code: 'AU_SUPER',
          total_contribution_tax: '1800.00',
          total_contributions: '12000.00',
          total_earnings: '6000.00',
          total_fees: '120.00',
          warnings: ['Projection is an estimate.'],
        },
      });
      return;
    }
    await route.abort();
  });

  await page.goto('/retirement');
  await page.getByRole('button', { name: 'Projection' }).click();
  const dialog = page.getByRole('dialog', {
    name: /browser super — projection/i,
  });
  await dialog.getByLabel('Projection date').fill('2027-01-01');
  await dialog.getByRole('button', { name: 'Calculate' }).click();
  await expect(dialog).toContainText('A$112,000.00');
  await expect(dialog).toContainText('using Australian superannuation');
  await expect(
    dialog.getByRole('button', { name: '1 projection warnings' }),
  ).toBeVisible();
});
