import { expect, test } from '@playwright/test';

const account = {
  display_name: 'Browser Owner',
  email: null,
  global_role: 'USER',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'owner',
};
const household = {
  currency: 'AUD',
  display_name: 'Browser household',
  id: 'dccc2857-cf74-4863-9f00-c99a9f815495',
  jurisdiction: 'AU',
};

test('selects a household and restores it after a new session', async ({
  page,
}) => {
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({ contentType: 'application/json', json: { account } }),
  );
  await page.route('**/api/v1/households', (route) =>
    route.fulfill({ contentType: 'application/json', json: [household] }),
  );
  await page.route('**/api/v1/reference/countries', (route) =>
    route.fulfill({ contentType: 'application/json', json: [] }),
  );
  await page.route('**/api/v1/reference/currencies', (route) =>
    route.fulfill({ contentType: 'application/json', json: [] }),
  );
  await page.route('**/api/v1/households/*/memberships', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: [
        {
          application_user_id: account.id,
          display_name: account.display_name,
          household_id: household.id,
          id: '00000000-0000-0000-0000-000000000020',
          is_active: true,
          role: 'OWNER',
          username: account.username,
        },
      ],
    }),
  );

  await page.goto('/households');
  await page.getByRole('button', { name: 'Use household' }).click();
  await expect(
    page.getByRole('heading', { name: 'Browser household members' }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Browser household members' }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Selected' })).toBeVisible();
});
