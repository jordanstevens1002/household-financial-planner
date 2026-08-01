import { expect, test } from '@playwright/test';

const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
const account = {
  display_name: 'Browser Owner',
  email: null,
  global_role: 'USER',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'owner',
};
const household = {
  currency: 'NZD',
  display_name: 'Browser household',
  id: householdId,
  jurisdiction: 'NZ',
};

test('creates and restores a household person', async ({ page }) => {
  const people: Record<string, unknown>[] = [];
  await page.addInitScript((id) => {
    localStorage.setItem('hfp.selection.household', id);
  }, householdId);
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({ contentType: 'application/json', json: { account } }),
  );
  await page.route('**/api/v1/households', (route) =>
    route.fulfill({ contentType: 'application/json', json: [household] }),
  );
  await page.route('**/api/v1/reference/countries', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: [
        {
          code: 'NZ',
          display_name: 'New Zealand',
          flag: '🇳🇿',
          recommended_currency: 'NZD',
        },
      ],
    }),
  );
  await page.route('**/api/v1/households/*/people', async (route) => {
    if (route.request().method() === 'POST') {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      people.push({
        ...payload,
        household_id: householdId,
        id: '85e30193-a324-4d22-9065-e25d819f6530',
      });
      await route.fulfill({
        contentType: 'application/json',
        json: people[0],
        status: 201,
      });
      return;
    }
    await route.fulfill({ contentType: 'application/json', json: people });
  });

  await page.goto('/people');
  await expect(page.getByText('No people recorded')).toBeVisible();
  await page.getByRole('button', { name: 'Add person' }).first().click();
  await page.getByLabel('Display name').fill('Taylor Example');
  await page.getByLabel('Tax residency (optional)').click();
  await page.getByText('🇳🇿 New Zealand').click();
  await page.getByRole('button', { name: 'Add person' }).click();

  await expect(page.getByText('Taylor Example')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Selected' })).toBeVisible();
  expect(people[0]).toMatchObject({
    display_name: 'Taylor Example',
    tax_jurisdiction: 'NZ',
    tax_residency_country: 'NZ',
  });
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem('hfp.selection.person')),
    )
    .toBe('85e30193-a324-4d22-9065-e25d819f6530');

  await page.reload();
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem('hfp.selection.person')),
    )
    .toBe('85e30193-a324-4d22-9065-e25d819f6530');
  await expect(page.getByRole('button', { name: 'Selected' })).toBeVisible();
});
