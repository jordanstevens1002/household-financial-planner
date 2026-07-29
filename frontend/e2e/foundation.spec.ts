import { expect, test } from '@playwright/test';

test('serves the React application shell at a desktop viewport', async ({
  page,
}) => {
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
