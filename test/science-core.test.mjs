import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { promisify } from 'node:util';
import { test } from 'node:test';
import {
  adjudicateNormalizations,
  deterministicId,
  normalizationInput,
  normalizeStructuralClaim,
  structuralHash,
  trueConfluences,
} from '../science/core.mjs';
import { validateGenerationPayload } from '../science/validation.mjs';

const execFileAsync = promisify(execFile);

async function generated(levels) {
  const generationId = `science-test-level-${levels}`;
  const { stdout } = await execFileAsync('python3', [
    new URL('../scripts/science-generate.py', import.meta.url).pathname,
    '--generation-id', generationId,
    '--levels', String(levels),
  ]);
  return JSON.parse(stdout);
}

function generation(payload) {
  return {
    id: payload.generation_id,
    maxdim: payload.experiment.maxdim,
    node_count: payload.structures.length,
    derivation_event_count: payload.derivation_events.length,
    true_confluence_count: trueConfluences(payload.derivation_events).length,
  };
}

test('controlled level-1 generation has full provenance and validates cleanly', async () => {
  const payload = await generated(1);
  const report = validateGenerationPayload(generation(payload), payload.structures, payload.derivation_events);
  assert.equal(report.clean, true, report.errors.join('\n'));
  assert.equal(report.counts.structures, 15);
  assert.equal(report.counts.admitted, 10);
  assert.equal(report.counts.generable, 5);
  assert.equal(report.counts.derivation_events, 5);
  assert.equal(report.methodology.self_duality.assessment, 'NOT_EVALUATED');
  assert.equal(payload.structures.every((item) => item.id === deterministicId('str', item.structural_hash)), true);
});

test('level-2 current-core scope contains no information-loss or self-transition events', async () => {
  const payload = await generated(2);
  const report = validateGenerationPayload(generation(payload), payload.structures, payload.derivation_events);
  assert.equal(report.clean, true, report.errors.join('\n'));
  assert.equal(report.integrity.cross_order_fiber_violations, 0);
  assert.equal(report.integrity.mixed_dual_product_violations, 0);
  assert.equal(report.integrity.mixed_dual_fiber_violations, 0);
  assert.equal(report.integrity.idempotent_self_transitions, 0);
});

test('binary input arity alone is not a true confluence', () => {
  const event = { output: 'x', event_hash: 'one', inputs: ['a', 'b'] };
  assert.deepEqual(trueConfluences([event]), []);
  assert.deepEqual(trueConfluences([event, event]), []);
  assert.deepEqual(trueConfluences([event, { ...event, event_hash: 'two', operator: 'other' }]), [{ output: 'x', derivation_event_count: 2 }]);
});

test('normalizer input excludes hidden targets, generator output and the peer result', () => {
  const input = normalizationInput({ id: 'c', domain: 'PHYSICS', name: 'n', formal_statement: 'f' }, [{ id: 'e', source_ref: 'https://example.test', fact: 'fact', quality: 'PRIMARY', content_hash: 'h' }]);
  const serialized = JSON.stringify(input);
  assert.doesNotMatch(serialized, /hidden_target_label|generator_output_payload|peer_normalization_payload/);
  assert.deepEqual(input.forbidden_inputs, ['other_normalization', 'hidden_target', 'generator_output', 'catalog_match']);
});

test('judge cannot invent a third normalization and disagreement is always disputed', () => {
  const a = { id: 'a', structural_claim: { kind: 'CYCLE', dim: 1 } };
  const b = { id: 'b', structural_claim: { kind: 'CYCLE', dim: 1 } };
  assert.throws(() => adjudicateNormalizations(a, b, { verdict: 'ACCEPT_NORMALIZATION', selected_normalization_id: 'c', reason: 'invented' }), /third normalization/);
  const disagreement = adjudicateNormalizations(a, { id: 'b', structural_claim: { kind: 'PRODUCT', dim: 1 } }, { verdict: 'ACCEPT_NORMALIZATION', selected_normalization_id: 'a', reason: 'ignore peer' });
  assert.equal(disagreement.verdict, 'AMBIGUOUS');
  assert.equal(disagreement.selected_normalization_id, null);
});

test('interpretive labels cannot change structural identity', () => {
  const structure = normalizeStructuralClaim({ kind: 'CYCLE', dim: 1, order: 0, mult: 1, dual: 0 });
  assert.equal(structuralHash(structure), structuralHash({ ...structure, label: 'ignored by caller' }));
  assert.throws(() => normalizeStructuralClaim({ ...structure, gravity: true }), /Unsupported structural fields/);
});

test('migration is additive, immutable and public-seal gated', async () => {
  const sql = await readFile(new URL('../schema/002_scientific_v1.sql', import.meta.url), 'utf8');
  assert.match(sql, /CREATE TABLE IF NOT EXISTS science_structures/);
  assert.match(sql, /CREATE TABLE IF NOT EXISTS science_derivation_events/);
  assert.match(sql, /CREATE TABLE IF NOT EXISTS science_interpretations/);
  assert.match(sql, /Frozen canon targets are immutable/);
  assert.match(sql, /Sealed generation .* is immutable/);
  assert.match(sql, /Public generation must be sealed and public eligible/);
  assert.doesNotMatch(sql, /ALTER\s+TABLE\s+(runs|structures|edges)\b/i);
  assert.doesNotMatch(sql, /UPDATE\s+(runs|structures|edges)\b/i);
  assert.doesNotMatch(sql, /DELETE\s+FROM\s+(runs|structures|edges)\b/i);
});
