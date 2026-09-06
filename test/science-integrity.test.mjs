import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { promisify } from 'node:util';
import { test } from 'node:test';
import { deterministicId, eventHash, eventIdentity, sha256, structuralHash,
  structuralSignature, trueConfluences } from '../science/core.mjs';
import { REPLAY_GRAMMAR_SHA256, REPLAY_OPERATOR_VERSION, REPLAY_OPERATORS } from '../science/replay.mjs';
import { validateGenerationPayload } from '../science/validation.mjs';

const exec = promisify(execFile);
async function generate(levels) {
  const { stdout } = await exec('python3', [new URL('../scripts/science-generate.py', import.meta.url).pathname,
    '--generation-id', 'integrity-audit', '--levels', String(levels), '--cap', '20000'], { maxBuffer: 32 * 1024 * 1024 });
  return JSON.parse(stdout);
}
function generation(p) {
  return { id: p.generation_id, grammar_hash: p.grammar_hash, maxdim: p.experiment.maxdim,
    expansion_levels: p.experiment.levels, node_count: p.structures.length,
    derivation_event_count: p.derivation_events.length,
    true_confluence_count: trueConfluences(p.derivation_events).length };
}
function validate(p) { return validateGenerationPayload(generation(p), p.structures, p.derivation_events); }
function sign(e) { e.event_hash = eventHash(e); e.id = deterministicId('dev', e.event_hash); }
function rejected(p, pattern) {
  const r = validate(p);
  assert.equal(r.clean, false, 'invalid payload must fail despite internally consistent hashes');
  assert.match(r.errors.join('\n'), pattern);
}
function replaceState(p, oldId, changes) {
  const s = p.structures.find((s) => s.id === oldId);
  Object.assign(s, changes);
  s.structural_sig = structuralSignature(s);
  s.structural_hash = structuralHash(s); s.id = deterministicId('str', s.structural_hash);
  for (const e of p.derivation_events) {
    e.inputs.forEach((id, i) => { if (id === oldId) { e.inputs[i] = s.id; e.input_structural_hashes[i] = s.structural_hash; } });
    if (e.output === oldId) { e.output = s.id; e.output_structural_hash = s.structural_hash; }
    sign(e);
  }
  return s;
}

test('verifier is pinned to the unchanged Python source, registry and canonical seeds', async () => {
  assert.equal(sha256(await readFile(new URL('../ckk_snapshot/ckk/gen/grammar.py', import.meta.url), 'utf8')), REPLAY_GRAMMAR_SHA256);
  const p = await generate(5);
  assert.deepEqual([...new Set(p.derivation_events.map((e) => e.operator))].sort(), [...REPLAY_OPERATORS].sort());
  assert.equal(p.derivation_events.every((e) => e.operator_version === REPLAY_OPERATOR_VERSION), true);
});

test('levels 2–5 agree with unchanged Python event identity and pass every replay', async () => {
  const expected = [[2, 52, 42, 0], [3, 204, 363, 133], [4, 604, 1543, 449], [5, 1403, 4491, 1084]];
  for (const [level, nodes, events, confluences] of expected) {
    const p = await generate(level);
    const r = validate(p);
    assert.equal(r.clean, true, r.errors.join('\n'));
    assert.equal(p.structures.length, nodes);
    assert.equal(p.derivation_events.length, events);
    assert.equal(r.counts.true_derivational_confluences, confluences);
    assert.equal(r.integrity.replayed_derivation_events, events);
    assert.equal(r.integrity.unreachable_generated_structures, 0);
    assert.equal(p.derivation_events.every((e) => e.event_hash === eventHash(e)), true);
  }
});

test('repeated observation and stale supplied hashes cannot inflate confluence', async () => {
  const p = await generate(2), e = p.derivation_events.find((e) => e.operator === 'op_close');
  const later = { ...e, level: e.level + 1, event_hash: 'arbitrary-new-digest' };
  assert.equal(eventHash(later), eventHash(e));
  assert.deepEqual(trueConfluences([e, later]), []);
  p.derivation_events.push(later);
  rejected(p, /duplicate derivation identity/);
});

test('product hashes normalize pairs; ordered fiber inputs remain ordered', () => {
  const e = { operator: 'op_product', operator_version: REPLAY_OPERATOR_VERSION,
    inputs: ['a', 'b'], input_structural_hashes: ['z', 'a'], output: 'out',
    output_structural_hash: 'hout', parameters: { arity: 2 }, level: 2 };
  const reversed = { ...e, inputs: [...e.inputs].reverse(), input_structural_hashes: [...e.input_structural_hashes].reverse() };
  assert.equal(eventHash(e), eventHash(reversed));
  assert.deepEqual(eventIdentity(e).input_structural_hashes, ['z', 'a']);
  assert.notEqual(eventHash({ ...e, input_structural_hashes: ['a', 'z'] }), eventHash(e));
  assert.notEqual(eventHash({ ...e, operator: 'op_fiber' }), eventHash({ ...reversed, operator: 'op_fiber' }));
});

test('well-hashed unknown operator, version, parameters and wrong arity fail replay', async () => {
  const initial = await generate(1);
  const probes = [
    [(e) => { e.operator = 'op_NOT_REGISTERED'; }, /unregistered operator/],
    [(e) => { e.operator_version = 'unreviewed-grammar'; }, /unsupported operator version/],
    [(e) => { e.parameters = { arity: 1, override: true }; }, /unsupported operator parameters/],
    [(e) => { e.inputs.push(e.inputs[0]); e.input_structural_hashes.push(e.input_structural_hashes[0]); }, /requires 1 inputs/],
  ];
  for (const [mutate, pattern] of probes) {
    const p = structuredClone(initial), e = p.derivation_events.find((e) => e.operator === 'op_close');
    mutate(e); sign(e); rejected(p, pattern);
  }
});

test('well-hashed op_close dimension 999 fails output replay', async () => {
  const p = await generate(1), e = p.derivation_events.find((e) => e.operator === 'op_close');
  replaceState(p, e.output, { dim: 999 });
  rejected(p, /replayed output signature mismatch/);
});

test('swapping product hashes alone fails even after recomputing its event hash', async () => {
  const p = await generate(4), e = p.derivation_events.find((e) => e.operator === 'op_product' && e.inputs[0] !== e.inputs[1]);
  assert.ok(e);
  e.input_structural_hashes.reverse(); sign(e);
  rejected(p, /input hash mismatch/);
});

test('a binary step must satisfy both parents and its order preconditions', async () => {
  const p = await generate(3), e = p.derivation_events.find((e) => e.operator === 'op_fiber');
  const input = p.structures.find((s) => s.id === e.inputs[0]);
  const other = p.structures.find((s) => s.kind === 'CYCLE' && s.recurrence_order !== input.recurrence_order
    && s.sym === input.sym && s.dual === input.dual && s.bc === input.bc);
  assert.ok(other);
  e.inputs[1] = other.id; e.input_structural_hashes[1] = other.structural_hash; sign(e);
  rejected(p, /operator preconditions do not hold/);
});

test('locally valid dual loops without admitted ancestors cannot prove a generation', async () => {
  const p = await generate(3);
  const forward = p.derivation_events.find((e) => e.operator === 'op_dual');
  const backward = p.derivation_events.find((e) => e.operator === 'op_dual' && e.output === forward.inputs[0] && e.inputs[0] === forward.output);
  assert.ok(backward);
  const ids = new Set([forward.output, backward.output]);
  p.structures = p.structures.filter((s) => ids.has(s.id));
  p.derivation_events = [forward, backward];
  rejected(p, /lack a seed-rooted replay/);
});

test('unadmitted seed changes, stale grammar pins and premature observations fail', async () => {
  const initial = await generate(1);
  const seed = structuredClone(initial);
  replaceState(seed, seed.structures.find((s) => s.kind === 'RECURRENCE').id, { recurrence_order: 99 });
  rejected(seed, /seed is not admitted/);
  const hash = structuredClone(initial); hash.grammar_hash = 'different-grammar';
  rejected(hash, /grammar hash has no supported replay/);
  const levels = await generate(2), e = levels.derivation_events.find((e) => e.operator === 'op_product');
  e.level = 1; sign(e);
  rejected(levels, /inputs are not derived before/);
});

test('missing binary co-input and malformed input arrays cannot validate', async () => {
  const p = await generate(3), e = p.derivation_events.find((e) => e.operator === 'op_product');
  const original = structuredClone(p);
  const originalGeneration = generation(original);
  e.inputs[0] = 'missing-parent'; sign(e);
  rejected(p, /dangling derivation inputs/);
  const bad = original.derivation_events.find((e) => e.operator === 'op_product');
  bad.input_structural_hashes = [];
  const report = validateGenerationPayload(originalGeneration, original.structures, original.derivation_events);
  assert.equal(report.clean, false);
  assert.match(report.errors.join('\n'), /parallel arrays/);
});
