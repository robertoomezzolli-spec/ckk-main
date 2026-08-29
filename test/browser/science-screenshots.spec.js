import { expect, test } from '@playwright/test';

async function open(page, path, marker) {
  await page.goto(path);
  await page.waitForFunction(() => window.__CKK_SCIENCE_READY__ === true);
  await expect(page.locator('#science-view')).toContainText(marker);
  const state = await page.evaluate(() => window.__CKK_SCIENCE_STATE__);
  expect(state.apiMode).toBe('SEALED_PREVIEW_EXPORT');
}

test('capture the complete Scientific v1 preview control plane', async ({ page }) => {
  await open(page, '/science', 'Evidence before generation');
  await page.screenshot({ path: 'screenshots/science-01-overview.png', fullPage: true });

  await open(page, '/science/queue', 'Candidate lifecycle');
  await page.screenshot({ path: 'screenshots/science-02-candidate-queue.png', fullPage: true });

  await open(page, '/science/disputes', 'GPT ↔ Claude disagreements');
  await page.screenshot({ path: 'screenshots/science-03-disputes.png', fullPage: true });

  await open(page, '/science/failures', 'Open structural limitations');
  await expect(page.locator('#science-view')).toContainText('BASE_RECURRENCE_ORDER_PRESERVATION');
  await page.screenshot({ path: 'screenshots/science-04-failures.png', fullPage: true });

  await open(page, '/science/grammar-pressure', 'Missing distinctions');
  await expect(page.locator('#science-view')).toContainText('HUMAN REVIEW ONLY');
  await page.screenshot({ path: 'screenshots/science-05-grammar-pressure.png', fullPage: true });

  await open(page, '/science/generations', 'Generation registry');
  await page.locator('[data-generation]').first().click();
  await expect(page.getByTestId('structure-inspector')).toContainText('VALIDATION');
  await page.screenshot({ path: 'screenshots/science-06-generation-inspector.png', fullPage: true });

  await page.getByRole('button', { name: 'Close inspector' }).click();
  await open(page, '/science/cross-domain', 'Cross-domain classes');
  await expect(page.locator('#science-view')).toContainText('No sealed Scientific structural hash');
  await page.screenshot({ path: 'screenshots/science-07-cross-domain.png', fullPage: true });

  await open(page, '/science/generations', 'Generation registry');
  await page.locator('[data-generation]').first().click();
  await page.locator('[data-structure]').first().click();
  await expect(page.getByTestId('structure-inspector')).toContainText('AGENT TRACE');
  await page.screenshot({ path: 'screenshots/science-08-structure-inspector.png', fullPage: true });
});

