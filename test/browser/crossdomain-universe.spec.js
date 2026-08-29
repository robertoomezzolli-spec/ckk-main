import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

const shots = 'screenshots';

async function enter(page) {
  await page.goto('/');
  await page.waitForFunction(() => window.__CKK_READY__ === true);
  await page.getByRole('button', { name: 'EXPLORE', exact: true }).click();
  await expect(page.locator('#landing')).toHaveClass(/hidden/);
  await page.waitForTimeout(900);
}

async function tourStep(page, number) {
  await page.getByRole('button', { name: 'GUIDED TOUR', exact: true }).first().click();
  for (let step = 1; step < number; step += 1) await page.getByRole('button', { name: 'NEXT' }).click();
  await page.getByRole('button', { name: 'OPEN STRUCTURE' }).click();
  await expect(page.getByTestId('node-card')).toBeVisible();
  await page.waitForTimeout(450);
}

test('sealed cross-domain universe renders and remains epistemically honest', async ({ page }) => {
  const fatal = [];
  page.on('pageerror', (error) => fatal.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') fatal.push(message.text()); });
  await enter(page);

  const state = await page.evaluate(() => window.__CKK_STATE__);
  expect(state).toMatchObject({ generationId: 'v6-noselfdual-563f50e328c5', runId: '34', nodes: 276, edges: 945, crossDomainBridges: 0 });
  await expect(page.getByTestId('domain-rail')).toContainText('PHYSICS');
  await expect(page.getByTestId('domain-rail')).toContainText('CHEMISTRY');
  await expect(page.getByTestId('domain-rail')).toContainText('BIOLOGY');
  await expect(page.getByTestId('domain-rail')).toContainText('COMPUTATION');
  await expect(page.locator('#universe')).toBeVisible();
  const canvasPixels = await page.locator('#universe').screenshot();
  expect(canvasPixels.byteLength).toBeGreaterThan(20_000);
  await page.screenshot({ path: `${shots}/01-universe-overview.png`, fullPage: true });

  await page.locator('[data-domain="physics"]').click();
  await expect(page.locator('#domain-panel')).toContainText('276');
  await page.screenshot({ path: `${shots}/02-physics-galaxy.png`, fullPage: true });

  for (const [domain, file] of [['chemistry', '03-chemistry-galaxy.png'], ['biology', '04-biology-galaxy.png'], ['computation', '05-computation-galaxy.png']]) {
    await page.locator(`[data-domain="${domain}"]`).click();
    await expect(page.locator('#domain-panel')).toContainText('MISSING EXECUTABLE DATA');
    await expect(page.locator('#domain-panel')).toContainText('Generated structures0');
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${shots}/${file}`, fullPage: true });
  }

  await page.locator('[data-domain="cross-domain"]').click();
  await expect(page.locator('#domain-panel')).toContainText('0 certified bridges');
  await expect(page.locator('#domain-panel')).toContainText('STRUCTURAL MATCH ONLY');
  await page.screenshot({ path: `${shots}/06-cross-domain-bridge.png`, fullPage: true });

  await tourStep(page, 5);
  await expect(page.getByTestId('node-card')).toContainText('REDISCOVERED');
  await expect(page.getByTestId('node-card')).toContainText('NOT EVALUATED');
  await page.screenshot({ path: `${shots}/07-rediscovered-node.png`, fullPage: true });

  await tourStep(page, 6);
  await expect(page.getByTestId('node-card')).toContainText('UNMATCHED');
  await expect(page.getByTestId('node-card')).toContainText('prioritization metrics, not evidence of new physics');
  await page.screenshot({ path: `${shots}/08-unmatched-node.png`, fullPage: true });

  await tourStep(page, 3);
  await expect(page.getByTestId('node-card')).toContainText('Bohr–Sommerfeld');
  await expect(page.getByTestId('node-card')).toContainText('GENERATED STRUCTURE ≠ INTERPRETATION');
  await page.screenshot({ path: `${shots}/09-physics-card.png`, fullPage: true });

  const knownFilter = page.locator('.filters input[value="KNOWN"]');
  await knownFilter.uncheck();
  await expect(knownFilter).not.toBeChecked();
  await knownFilter.check();
  await page.getByRole('button', { name: 'ADVANCED DATA' }).click();
  await expect(page.locator('body')).toHaveClass(/advanced/);
  expect(fatal).toEqual([]);
});

test('guided tour advances and open questions remain explicit', async ({ page }) => {
  await enter(page);
  await page.getByRole('button', { name: 'GUIDED TOUR', exact: true }).first().click();
  await expect(page.getByTestId('tour-card')).toContainText('STEP 1 / 7');
  await page.getByRole('button', { name: 'NEXT' }).click();
  await expect(page.getByTestId('tour-card')).toContainText('STEP 2 / 7');
  await page.getByRole('button', { name: 'OPEN QUESTIONS', exact: true }).click();
  await expect(page.locator('#domain-panel')).toContainText('1,836 cross-order fiber events');
  await expect(page.locator('#domain-panel')).toContainText('New generationNOT CREATED');
});

test('a direct 3D node click opens its scientific card', async ({ page }) => {
  await enter(page);
  const point = await page.evaluate(() => window.__CKK_DEBUG__.visibleNodePositions().find((node) => node.visible && node.x > 280 && node.x < 1100 && node.y > 130 && node.y < 850));
  expect(point).toBeTruthy();
  await page.mouse.click(point.x, point.y);
  await expect(page.getByTestId('node-card')).toBeVisible();
  await expect(page.getByTestId('node-card')).toContainText(/STRUCTURAL d\d/);
});

test('WebGL2 failure exposes a readable non-scientific fallback', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, 'WebGL2RenderingContext', { configurable: true, value: undefined }); });
  await page.goto('/');
  await page.waitForFunction(() => window.__CKK_READY__ === true);
  await expect(page.locator('#fallback')).toBeVisible();
  await expect(page.locator('#fallback')).toContainText('3D view unavailable');
  await expect(page.locator('#fallback')).toContainText('PHYSICS');
  await expect(page.locator('#fallback')).toContainText('CHEMISTRY');
  await expect(page.locator('#fallback')).toContainText('BIOLOGY');
  await expect(page.locator('#fallback')).toContainText('COMPUTATION');
});

test('instanced universe meets the browser smoke-performance floor', async ({ page, browserName }) => {
  await enter(page);
  const metrics = await page.evaluate(async () => {
    const samples = [];
    let previous = performance.now();
    await new Promise((resolve) => {
      const frame = (now) => {
        samples.push(now - previous); previous = now;
        if (samples.length >= 120) resolve(); else requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    });
    const sorted = [...samples].sort((a, b) => a - b);
    const resources = performance.getEntriesByType('resource');
    return {
      measured_at: new Date().toISOString(),
      app_ready_ms_from_navigation: Math.round(window.__CKK_READY_AT__),
      frames_sampled: samples.length,
      mean_frame_ms: samples.reduce((sum, value) => sum + value, 0) / samples.length,
      p95_frame_ms: sorted[Math.floor(sorted.length * .95)],
      mean_fps: 1000 / (samples.reduce((sum, value) => sum + value, 0) / samples.length),
      encoded_resource_bytes: resources.reduce((sum, item) => sum + (item.encodedBodySize || 0), 0),
      resource_count: resources.length,
      webgl2: Boolean(document.createElement('canvas').getContext('webgl2')),
      app_state: window.__CKK_STATE__,
      rendering: { node_primitive: 'THREE.InstancedMesh', nodes: 276, relation_segments: 1890 },
    };
  });
  metrics.browser = browserName;
  metrics.viewport = { width: 1600, height: 1000 };
  metrics.environment = 'Headless Google Chrome with SwiftShader WebGL; conservative CI smoke measurement, not a hardware benchmark.';
  expect(metrics.webgl2).toBe(true);
  expect(metrics.mean_fps).toBeGreaterThan(20);
  expect(metrics.p95_frame_ms).toBeLessThan(100);
  const json = JSON.stringify(metrics, null, 2) + '\n';
  const markdown = `# Cross-Domain Universe Performance\n\n- Browser: ${metrics.browser}\n- Viewport: 1600 × 1000\n- WebGL2: ${metrics.webgl2}\n- App ready: ${metrics.app_ready_ms_from_navigation} ms from navigation\n- Nodes: ${metrics.app_state.nodes} (instanced)\n- Relations: ${metrics.app_state.edges}\n- Mean frame time: ${metrics.mean_frame_ms.toFixed(2)} ms\n- P95 frame time: ${metrics.p95_frame_ms.toFixed(2)} ms\n- Mean FPS: ${metrics.mean_fps.toFixed(1)}\n- Encoded resources: ${metrics.encoded_resource_bytes} bytes across ${metrics.resource_count} requests\n\n${metrics.environment}\n`;
  await writeFile(new URL('../../audit/crossdomain-performance.json', import.meta.url), json, 'utf8');
  await writeFile(new URL('../../audit/crossdomain-performance.md', import.meta.url), markdown, 'utf8');
});
