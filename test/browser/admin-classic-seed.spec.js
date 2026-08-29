import { expect, test } from '@playwright/test';

async function mockAdmin(page, key = 'browser-admin-audit-key') {
  await page.route('**/.netlify/functions/admin-session', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ admin: true, preference_key: key }),
  }));
}

async function enter(page) {
  await page.goto('/');
  await page.waitForFunction(() => window.__CKK_READY__ === true);
  await page.getByRole('button', { name: 'EXPLORE', exact: true }).click();
}

test('admin Classic Fan link renders the exact same selected SEALED generation and node identities', async ({ page }) => {
  await mockAdmin(page);
  await enter(page);
  await expect(page.getByTestId('admin-tools')).toBeVisible();
  const audit = await page.evaluate(() => ({
    same: window.__CKK_VIEW_AUDIT__.sameDataReference(),
    generation: window.__CKK_VIEW_AUDIT__.generation(),
    ids: window.__CKK_VIEW_AUDIT__.nodeIds(),
  }));
  expect(audit.same).toBe(true);
  expect(new Set(Object.values(audit.generation))).toEqual(new Set(['v6-noselfdual-563f50e328c5']));
  expect(audit.ids.selected).toEqual(audit.ids.universe);
  expect(audit.ids.selected).toEqual(audit.ids.classic);

  await page.getByTestId('admin-view-link').click();
  await expect(page.getByTestId('classic-fan')).toBeVisible();
  await expect(page.getByTestId('admin-view-link')).toHaveText('UNIVERSE 3D');
  await expect(page.getByTestId('classic-fan')).toContainText('276structures');
  await expect(page.getByTestId('classic-fan')).toContainText('945relations');

  await page.locator('[data-known-id="151"]').click();
  await expect(page.locator('[data-classic-detail]')).toBeVisible();
  await expect(page.locator('[data-classic-detail]')).toContainText('Bohr–Sommerfeld');
  await expect(page.locator('[data-classic-detail]')).toContainText('INSPECT STRUCTURE IN SCIENTIFIC');

  await page.reload();
  await page.waitForFunction(() => window.__CKK_READY__ === true);
  expect(await page.evaluate(() => window.__CKK_VIEW_AUDIT__.activeView())).toBe('classic');
  await expect(page.getByTestId('classic-fan')).toBeVisible();
});

test('admin Seed Explorer is read-only and fails closed for the E = mc² blind probe', async ({ page }) => {
  await mockAdmin(page, 'seed-admin-audit-key');
  const mutationRequests = [];
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) mutationRequests.push(`${request.method()} ${request.url()}`);
  });
  await enter(page);
  await expect(page.locator('#seed-expression')).toHaveValue('E = mc²');
  await page.getByRole('button', { name: 'EXPLORE SEED' }).click();
  await expect(page.getByTestId('seed-result')).toBeVisible();
  await expect(page.getByTestId('seed-result')).toContainText('E = mc²');
  await expect(page.getByTestId('seed-result')).toContainText('NO STRUCTURAL PATH');
  await expect(page.getByTestId('seed-result')).toContainText('No generated node is explicitly attached');
  const result = await page.evaluate(() => window.__CKK_VIEW_AUDIT__.seedResult());
  expect(result.verdict).toBe('NO_STRUCTURAL_PATH');
  expect(result.matchedNodes).toEqual([]);
  expect(mutationRequests).toEqual([]);

  await page.getByTestId('admin-view-link').click();
  await expect(page.getByTestId('classic-fan')).toBeVisible();
  await page.getByRole('button', { name: 'EXPLORE SEED' }).click();
  await expect(page.locator('.classic-graph')).toHaveClass(/no-path-pulse/);
});

test('view controls and Seed Explorer remain hidden from non-admin users', async ({ page }) => {
  await page.route('**/.netlify/functions/admin-session', (route) => route.fulfill({ status: 401, contentType: 'application/json', body: '{"admin":false}' }));
  await enter(page);
  await expect(page.getByTestId('admin-tools')).toBeHidden();
  await expect(page.getByTestId('seed-explorer')).toBeHidden();
  await expect(page.getByTestId('admin-view-link')).toBeVisible();
  await page.getByTestId('admin-view-link').click();
  await expect(page.getByTestId('classic-fan')).toBeVisible();
});
