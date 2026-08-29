import { expect, test } from '@playwright/test';

const generation = {
  id: 'sci-v1-browser-fixture', status: 'SEALED', preview: true, public_eligible: false,
  node_count: 2, derivation_event_count: 1, true_confluence_count: 0, maxdim: 4, expansion_levels: 1,
  grammar_hash: 'grammar-fixture-hash', seed_set_hash: 'seed-fixture-hash',
  validation_report: { clean: true, methodology: { self_duality: { assessment: 'NOT_EVALUATED' } } },
};
const structures = [
  { generation_id: generation.id, id: 'str-a', kind: 'RECURRENCE', dim: 0, recurrence_order: 0, lifecycle: 'ADMITTED', structural_hash: 'hash-a', structural_sig: { kind: 'RECURRENCE', dim: 0 } },
  { generation_id: generation.id, id: 'str-b', kind: 'CYCLE', dim: 1, recurrence_order: 0, lifecycle: 'GENERABLE', structural_hash: 'hash-b', structural_sig: { kind: 'CYCLE', dim: 1 } },
];
const event = { generation_id: generation.id, id: 'dev-a', operator: 'op_close', operator_version: 'fixture', inputs: ['str-a'], output: 'str-b', input_structural_hashes: ['hash-a'], output_structural_hash: 'hash-b', level: 1 };

const responses = {
  overview: { schema: 'ckk.science-overview.v1', generation_status: [{ status: 'SEALED', count: 1 }], candidate_status: [{ status: 'SEALED', count: 1 }], failure_status: [{ code: 'SIGNATURE_COLLISION', count: 2 }], agent_status: [], public_state: { active_generation_id: null }, historical_run34: { generation_id: 'v6-noselfdual-563f50e328c5', run_id: 34, nodes: 276, edges: 945, historical_graph_confluences: 196 } },
  candidates: { candidates: [{ id: 'cand-a', name: 'Browser contract fixture', domain: 'PHYSICS', status: 'SEALED', evidence_count: 1, normalization_count: 2 }] },
  disputes: { disputes: [] },
  failures: { failures: [{ id: 'failure-a', code: 'SIGNATURE_COLLISION', domain: 'PHYSICS', missing_distinction: 'BASE_RECURRENCE_ORDER_PRESERVATION', details: { summary: 'Audited core finding.' } }] },
  'grammar-pressure': { groups: [{ missing_distinction: 'EXECUTABLE_DOMAIN_FIXTURE', domains: ['BIOLOGY', 'CHEMISTRY', 'COMPUTATION'], failure_count: 3 }], proposals: [], automatic_activation: 'FORBIDDEN' },
  generations: { generations: [generation] },
  'cross-domain': { matches: [] },
  [`generations/${generation.id}`]: { generation, structures, derivation_events: [event], interpretations: [], seal: { public_eligible: false } },
  [`structures/str-b`]: { structure: structures[1], derivation_events: { incoming: [event], outgoing: [] }, interpretations: [], agent_trace: [] },
};

async function mockApi(page) {
  await page.route('**/api/science/**', async (route) => {
    const url = new URL(route.request().url());
    const key = url.pathname.replace('/api/science/', '');
    await route.fulfill({ status: responses[key] ? 200 : 404, contentType: 'application/json', body: JSON.stringify(responses[key] ?? { error: 'not found' }) });
  });
}

test('Scientific control plane renders all required views without merging truth layers', async ({ page }) => {
  for (const [path, marker] of [
    ['/science', 'Evidence before generation'], ['/science/queue', 'Candidate lifecycle'], ['/science/disputes', 'GPT ↔ Claude disagreements'],
    ['/science/failures', 'Open structural limitations'], ['/science/grammar-pressure', 'Missing distinctions'],
    ['/science/generations', 'Generation registry'], ['/science/cross-domain', 'Cross-domain classes'],
  ]) {
    await mockApi(page);
    await page.goto(path);
    await page.waitForFunction(() => window.__CKK_SCIENCE_READY__ === true);
    await expect(page.locator('#science-view')).toContainText(marker);
    await expect(page.locator('.nav-law')).toContainText('STRUCTURE');
    await expect(page.locator('.nav-law')).toContainText('DERIVATION');
    await expect(page.locator('.nav-law')).toContainText('INTERPRETATION');
  }
});

test('generation and structure inspectors expose provenance, hashes and agent trace', async ({ page }) => {
  await mockApi(page);
  await page.goto('/science/generations');
  await page.waitForFunction(() => window.__CKK_SCIENCE_READY__ === true);
  await page.locator('[data-generation]').click();
  await expect(page.getByTestId('structure-inspector')).toBeVisible();
  await expect(page.getByTestId('structure-inspector')).toContainText('VALIDATION');
  await page.locator('[data-structure="str-b"]').click();
  await expect(page.getByTestId('structure-inspector')).toContainText('DERIVATION EVENTS');
  await expect(page.getByTestId('structure-inspector')).toContainText('INTERPRETATIONS');
  await expect(page.getByTestId('structure-inspector')).toContainText('AGENT TRACE');
});

