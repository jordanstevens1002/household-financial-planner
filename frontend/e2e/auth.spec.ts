import { expect, test, type Page } from '@playwright/test';

const account = {
  display_name: 'Browser Administrator',
  email: null,
  global_role: 'ADMIN',
  id: '00000000-0000-0000-0000-000000000001',
  must_change_password: false,
  username: 'administrator',
};

async function unauthenticated(page: Page, bootstrapRequired = false) {
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { detail: 'Authentication required' },
      status: 401,
    }),
  );
  await page.route('**/api/v1/auth/status', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { bootstrap_required: bootstrapRequired },
    }),
  );
}

test('bootstraps the first administrator', async ({ page }) => {
  await unauthenticated(page, true);
  await page.route('**/api/v1/auth/bootstrap', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { account, csrf_token: 'csrf-token' },
      status: 201,
    }),
  );
  await page.goto('/properties');
  await page.getByLabel('Username').fill('administrator');
  await page.getByLabel('Bootstrap token').fill('operator-bootstrap-token');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Create administrator' }).click();
  await expect(page.getByRole('heading', { name: 'Properties' })).toBeVisible();
  await expect(page.getByText('No household selected')).toBeVisible();
  await expect(page).toHaveURL(/\/properties$/);
});

test('shows login failure and then restores the intended route', async ({
  page,
}) => {
  await unauthenticated(page);
  let attempts = 0;
  await page.route('**/api/v1/auth/login', (route) => {
    attempts += 1;
    return route.fulfill(
      attempts === 1
        ? {
            contentType: 'application/json',
            json: { detail: 'Invalid username or password' },
            status: 401,
          }
        : { contentType: 'application/json', json: { account } },
    );
  });
  await page.goto('/retirement');
  await page.getByLabel('Username').fill('administrator');
  await page.getByLabel('Password').fill('incorrect password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Invalid username or password',
  );
  await expect(page.getByLabel('Username')).toHaveValue('administrator');
  await expect(page.getByLabel('Password')).toHaveValue('');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(
    page.getByRole('heading', { name: 'Retirement is coming soon' }),
  ).toBeVisible();
});

test('forces a password change and supports logout', async ({ page }) => {
  let forced = true;
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { account: { ...account, must_change_password: forced } },
    }),
  );
  await page.route('**/api/v1/auth/password/change', (route) => {
    forced = false;
    return route.fulfill({
      contentType: 'application/json',
      json: { account },
    });
  });
  await page.route('**/api/v1/auth/logout', (route) =>
    route.fulfill({ status: 204 }),
  );
  await page.route('**/api/v1/auth/status', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { bootstrap_required: false },
    }),
  );
  await page.goto('/');
  await page.getByLabel('Temporary password').fill('temporary password');
  await page
    .getByLabel('New password', { exact: true })
    .fill('replacement password');
  await page.getByLabel('Confirm new password').fill('replacement password');
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(
    page.getByRole('heading', { name: 'Household overview' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
});

test('returns to login when an active session expires', async ({ page }) => {
  await page.clock.install();
  let sessionChecks = 0;
  await page.route('**/api/v1/auth/session', (route) => {
    sessionChecks += 1;
    return route.fulfill(
      sessionChecks === 1
        ? { contentType: 'application/json', json: { account } }
        : {
            contentType: 'application/json',
            json: { detail: 'Session expired or invalid' },
            status: 401,
          },
    );
  });
  await page.route('**/api/v1/auth/status', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { bootstrap_required: false },
    }),
  );
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Household overview' }),
  ).toBeVisible();
  await page.clock.fastForward(60_000);
  await expect(
    page.getByText('Your session expired. Sign in again to continue.'),
  ).toBeVisible();
});
