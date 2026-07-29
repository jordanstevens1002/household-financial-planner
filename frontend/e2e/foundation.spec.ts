import { expect, test } from '@playwright/test';

test('serves the React foundation at a desktop viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Household Financial Planner' }),
  ).toBeVisible();
  await expect(page.getByText('React v2 foundation')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'About this preview' }),
  ).toBeVisible();
});
