import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { FAILURE_CODES } from '../science/core.mjs';

const seedUrl = new URL('../audit/canonical-replacement/seed.v1.json', import.meta.url);

test('canonical replacement seed is a fail-closed missing-operator gate', async () => {
  const seed = JSON.parse(await readFile(seedUrl, 'utf8'));
  assert.equal(seed.status, 'OPEN_HARD_GATE');
  assert.equal(seed.target.name, 'canonical_replacement');
  assert.ok(FAILURE_CODES.includes('MISSING_OPERATOR'));
  assert.match(seed.target.required_provenance, /MISSING_OPERATOR/);
  assert.match(seed.success_criterion, /sealed before any external measurement\/lookup/);
});

test('canonical replacement seed forbids importing the desired physics', async () => {
  const seed = JSON.parse(await readFile(seedUrl, 'utf8'));
  const forbidden = seed.forbidden_shortcuts.join('\n');
  assert.match(forbidden, /Partner blocking as collapse/i);
  assert.match(forbidden, /Landauer heat as an outcome selector/i);
  assert.match(forbidden, /projective measurement or Born sampling/i);
  assert.match(forbidden, /CODATA value/i);
  assert.match(forbidden, /post-hoc matching/i);
});

test('known 1\/5 result remains classified as combinatorial control, not nature', async () => {
  const seed = JSON.parse(await readFile(seedUrl, 'utf8'));
  const block = seed.known_results.partner_memory_blocking;
  assert.equal(block.result, 'p_block(N)=1/(2N-3) for the explicitly specified uniform random-pair scheduler');
  assert.equal(block.classification, 'EXACT_COMBINATORIAL_CONTROL');
  assert.equal(block.physics_claim, 'NONE');
});
