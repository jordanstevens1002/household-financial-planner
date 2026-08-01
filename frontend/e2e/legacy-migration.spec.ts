import { expect, test, type Page } from '@playwright/test';

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

const localUser = {
  ...administrator,
  display_name: 'Alex Local',
  global_role: 'USER',
  id: '00000000-0000-0000-0000-000000000002',
  username: 'alex-local',
};

function identity(
  id: string,
  status: 'ACTIVATION_PENDING' | 'READY' | 'UNMAPPED' = 'UNMAPPED',
) {
  return {
    captured_at: '2026-07-30T00:00:00Z',
    display_name: id === 'legacy-1' ? 'Alex Legacy' : 'Taylor Legacy',
    email: `${id}@example.test`,
    id,
    mapping:
      status === 'UNMAPPED'
        ? null
        : {
            application_user_id: localUser.id,
            display_name: localUser.display_name,
            id: `mapping-${id}`,
            last_reconciled_at: '2026-08-01T00:00:00Z',
            mapped_at: '2026-08-01T00:00:00Z',
            mapped_by_application_user_id: administrator.id,
            username: localUser.username,
          },
    memberships: [
      {
        household_id: '00000000-0000-0000-0000-000000000010',
        household_name: 'Alex household',
        role: 'OWNER',
      },
    ],
    oidc_subject: `oidc|${id}`,
    status,
  };
}

function list(identities: ReturnType<typeof identity>[]) {
  const unresolved = identities.filter((item) => item.status !== 'READY');
  return {
    activation_pending_count: unresolved.filter(
      (item) => item.status === 'ACTIVATION_PENDING',
    ).length,
    cutover_ready: unresolved.length === 0,
    identities,
    unresolved_count: unresolved.length,
  };
}

async function mockSession(page: Page) {
  await page.route('**/api/v1/auth/session', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: { account: administrator },
    }),
  );
  await page.route('**/api/v1/admin/users', (route) =>
    route.fulfill({
      contentType: 'application/json',
      json: [administrator, localUser],
    }),
  );
}

test('completes a confirmed mapping and reports cutover readiness', async ({
  page,
}) => {
  await mockSession(page);
  let identities = [identity('legacy-1')];
  await page.route('**/api/v1/admin/legacy-identities**', async (route) => {
    const request = route.request();
    if (request.method() === 'POST' && request.url().endsWith('/mapping')) {
      identities = [identity('legacy-1', 'READY')];
      await route.fulfill({
        contentType: 'application/json',
        json: { identity: identities[0], temporary_password: null },
        status: 201,
      });
      return;
    }
    await route.fulfill({
      contentType: 'application/json',
      json: list(identities),
    });
  });

  await page.goto('/administration/legacy-identities');
  await expect(page.getByText('0 of 1 ready')).toBeVisible();
  await page.getByRole('button', { name: 'Map login' }).click();
  await page.getByLabel('Local account').click();
  await page.getByRole('option', { name: /Alex Local/ }).click();
  await page.getByRole('button', { name: 'Review mapping' }).click();
  await expect(
    page.getByRole('heading', { name: 'Confirm identity mapping' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Confirm mapping' }).click();

  await expect(page.getByText('1 of 1 ready')).toBeVisible();
  await expect(
    page.getByText('Every legacy login has a usable local account.'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Complete review' }).click();
  await expect(
    page.getByText(
      'Every captured legacy login is mapped to a usable local account.',
    ),
  ).toBeVisible();
});

test('blocks a partial migration until login loss is explicitly accepted', async ({
  page,
}) => {
  await mockSession(page);
  const identities = [
    identity('legacy-1', 'READY'),
    identity('legacy-2', 'ACTIVATION_PENDING'),
  ];
  await page.route('**/api/v1/admin/legacy-identities**', (route) =>
    route.fulfill({ contentType: 'application/json', json: list(identities) }),
  );

  await page.goto('/administration/legacy-identities');
  await expect(page.getByText('1 of 2 ready')).toBeVisible();
  const complete = page.getByRole('button', { name: 'Complete review' });
  await expect(complete).toBeDisabled();
  await page
    .getByLabel('Accept that 1 unresolved login(s) will lose access')
    .check();
  await expect(complete).toBeEnabled();
  await complete.click();
  await expect(
    page.getByText('You accepted that 1 unresolved login(s) may lose access.'),
  ).toBeVisible();
});

test('keeps a conflicting mapping unresolved and displays the API result', async ({
  page,
}) => {
  await mockSession(page);
  const identities = [identity('legacy-1')];
  await page.route('**/api/v1/admin/legacy-identities**', async (route) => {
    if (
      route.request().method() === 'POST' &&
      route.request().url().endsWith('/mapping')
    ) {
      await route.fulfill({
        contentType: 'application/json',
        json: { detail: 'Legacy identity is already mapped' },
        status: 409,
      });
      return;
    }
    await route.fulfill({
      contentType: 'application/json',
      json: list(identities),
    });
  });

  await page.goto('/administration/legacy-identities');
  await page.getByRole('button', { name: 'Map login' }).click();
  await page.getByLabel('Local account').click();
  await page.getByRole('option', { name: /Alex Local/ }).click();
  await page.getByRole('button', { name: 'Review mapping' }).click();
  await page.getByRole('button', { name: 'Confirm mapping' }).click();

  await expect(
    page.getByText('Legacy identity is already mapped'),
  ).toBeVisible();
  await expect(page.getByText('0 of 1 ready')).toBeVisible();
});
