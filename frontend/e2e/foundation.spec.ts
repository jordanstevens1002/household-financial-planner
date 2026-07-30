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
  await expect(
    page.getByRole('heading', { name: 'Properties is coming next' }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/properties$/);
});
