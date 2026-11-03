import { expect, test } from '@playwright/test';

test('filters the household timeline in a desktop browser', async ({
  page,
}) => {
  const householdId = 'dccc2857-cf74-4863-9f00-c99a9f815495';
  await page.addInitScript((id) => {
    localStorage.setItem('hfp.selection.household', id);
  }, householdId);
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/auth/session')) {
      await route.fulfill({
        json: {
          account: {
            display_name: 'Browser Viewer',
            global_role: 'USER',
            id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
            must_change_password: false,
            username: 'timeline-viewer',
          },
        },
      });
      return;
    }
    if (url.pathname.endsWith('/households')) {
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
    if (url.pathname.endsWith(`/households/${householdId}/timeline`)) {
      await route.fulfill({
        json: {
          data_quality_flags: ['FUTURE_OBSERVED_EVENT'],
          events: [
            {
              amount: '500000.00',
              classification: 'OBSERVED',
              created_by_user_id: 'cf3c01a8-b3cc-4c09-a504-ed193c290744',
              data_quality_flags: ['FUTURE_OBSERVED_EVENT'],
              effective_at: '2026-11-03T00:00:00Z',
              event_priority: 10,
              event_type_code: 'PROPERTY_VALUED',
              event_type_id: '16b3f01b-ff76-451f-a4bd-a2ddf89834fd',
              household_id: householdId,
              id: '79fe9e91-0d62-4793-bdd2-c47befbf84ad',
              idempotency_key: null,
              is_enabled: true,
              loan_id: null,
              notes: 'Browser valuation',
              payload: {},
              percentage: null,
              person_id: null,
              property_id: '87496ae2-6bed-426d-854f-3eb04843ae12',
              recorded_at: '2026-11-03T01:00:00Z',
            },
          ],
          household_id: householdId,
        },
      });
      return;
    }
    await route.abort();
  });

  await page.goto('/timeline');
  await expect(page.getByRole('heading', { name: 'Timeline' })).toBeVisible();
  await expect(page.getByText('Property Valued')).toBeVisible();
  await page.getByLabel('From').fill('2026-01-01');
  await page.getByLabel('To').fill('2026-12-31');
  await page.getByLabel('Include disabled events').check();
  const request = page.waitForRequest((candidate) => {
    const url = new URL(candidate.url());
    return (
      url.pathname.endsWith(`/households/${householdId}/timeline`) &&
      url.searchParams.get('from_date') === '2026-01-01' &&
      url.searchParams.get('to_date') === '2026-12-31' &&
      url.searchParams.get('include_disabled') === 'true'
    );
  });
  await page.getByRole('button', { name: 'Refresh timeline' }).click();
  await request;
});
