import { expect, test } from '@playwright/test';

test('serves the React application shell at a desktop viewport', async ({
  page,
}) => {
  await page.route('**/api/v1/auth/session', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      json: {
        account: {
          display_name: 'Browser User',
          email: null,
          global_role: 'USER',
          id: '00000000-0000-0000-0000-000000000001',
          must_change_password: false,
          username: 'browser-user',
        },
      },
    });
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Household overview' }),
  ).toBeVisible();
  await expect(page.getByRole('navigation')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'About this preview' }),
  ).toBeVisible();

  await page.getByRole('link', { name: 'Properties' }).click();
  await expect(page.getByRole('heading', { name: 'Properties' })).toBeVisible();
  await expect(page.getByText('No household selected')).toBeVisible();
  await expect(page).toHaveURL(/\/properties$/);
});

test('shows installation health and provider metadata in settings', async ({
  page,
}) => {
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: {
        account: {
          display_name: 'Browser User',
          email: null,
          global_role: 'USER',
          id: '00000000-0000-0000-0000-000000000001',
          must_change_password: false,
          username: 'browser-user',
        },
      },
    }),
  );
  await page.route('**/health/live', (route) =>
    route.fulfill({ json: { status: 'ok', version: '1.0.0' } }),
  );
  await page.route('**/api/v1/system/status', (route) =>
    route.fulfill({ json: { status: 'ready', version: '1.0.0' } }),
  );
  await page.route('**/api/v1/reference/countries', (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route('**/api/v1/reference/currencies', (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route('**/api/v1/tax-providers', (route) =>
    route.fulfill({
      json: [
        {
          display_name: 'Browser tax provider',
          jurisdiction: 'EX',
          supported_tax_years: ['2026'],
        },
      ],
    }),
  );
  await page.route('**/api/v1/retirement-providers', (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route('**/api/v1/purchase-providers', (route) =>
    route.fulfill({ json: [] }),
  );

  await page.goto('/settings');

  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect(page.getByText('API available')).toBeVisible();
  await expect(page.getByText('Database ready')).toBeVisible();
  await expect(page.getByText('Application version: 1.0.0')).toBeVisible();
  await expect(page.getByText('Browser tax provider')).toBeVisible();
});
