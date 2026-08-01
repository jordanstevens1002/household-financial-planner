import { expect, test } from '@playwright/test';

const administrator = {
  created_at: '2026-07-30T00:00:00Z',
  display_name: 'Browser Administrator',
  email: null,
  global_role: 'ADMIN',
  id: '00000000-0000-0000-0000-000000000001',
  is_active: true,
  must_change_password: false,
  password_expires_at: null,
  username: 'administrator',
};

test('creates a local user and hands off its temporary password once', async ({
  page,
}) => {
  const users = [administrator];
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { account: administrator },
    }),
  );
  await page.route('**/api/v1/admin/users', async (route) => {
    if (route.request().method() === 'POST') {
      const created = {
        ...administrator,
        display_name: 'Browser User',
        global_role: 'USER',
        id: '00000000-0000-0000-0000-000000000002',
        must_change_password: true,
        username: 'browser-user',
      };
      users.push(created);
      await route.fulfill({
        contentType: 'application/json',
        json: { account: created, temporary_password: 'one-time-password' },
        status: 201,
      });
      return;
    }
    await route.fulfill({ contentType: 'application/json', json: users });
  });

  await page.goto('/administration');
  await expect(
    page.getByRole('heading', { name: 'User administration' }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'User administration' }),
  ).toBeVisible();
  await expect(
    page.getByText(/household membership separately controls access/i),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Add user' }).click();
  await page.getByLabel('Username').fill('browser-user');
  await page.getByLabel('Display name').fill('Browser User');
  await page.getByRole('button', { name: 'Create user' }).click();
  await expect(page.getByLabel('One-time secret')).toHaveValue(
    'one-time-password',
  );
  await page.getByRole('button', { name: 'I have saved it' }).click();
  await expect(page.getByLabel('One-time secret')).toBeHidden();
  await expect(page.getByText('browser-user')).toBeVisible();
});
