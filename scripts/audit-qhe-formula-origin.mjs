// External claim audit. The Python generator receives no formula or target.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { structuralHash, structuralSignature, trueConfluences, sha256 } from '../science/core.mjs';
import { validateGenerationPayload } from '../science/validation.mjs';
import { buildPhysicsCardModel } from '../site/physics-cards.js';

const payload = JSON.parse(execFileSync('python3', [fileURLToPath(new URL('./science-generate.py', import.meta.url)),
  '--generation-id', 'qhe-formula-origin-20260906', '--levels', '5', '--cap', '20000'],
  { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 }));
const validation = validateGenerationPayload({ id: payload.generation_id, grammar_hash: payload.grammar_hash,
  maxdim: payload.experiment.maxdim, expansion_levels: payload.experiment.levels,
  node_count: payload.structures.length, derivation_event_count: payload.derivation_events.length,
  true_confluence_count: trueConfluences(payload.derivation_events).length }, payload.structures, payload.derivation_events);
assert.equal(validation.clean, true, validation.errors.join('\n'));
// Read interpretation only after the independent generation has finished.
const archive = JSON.parse(readFileSync(new URL('../audit/qhe4d-archived-claim-20260906.json', import.meta.url)));
const card = buildPhysicsCardModel(archive.node, { nodes: [archive.node], edges: [] });
assert.equal(card.formulaSource, 'PHYSICS ANNOTATION');
const parent = new Map(), reached = new Set(payload.structures.filter(s => s.lifecycle === 'ADMITTED').map(s => s.id));
const byId = new Map(payload.structures.map(s => [s.id, s]));
for (const e of payload.derivation_events) {
  if (!reached.has(e.output) && e.inputs.every(id => reached.has(id))) {
    reached.add(e.output); parent.set(e.output, e);
  }
}
function trace(target) {
  const nodes = new Map(), events = new Map();
  function visit(id) {
    if (nodes.has(id)) return;
    const s = byId.get(id); assert.ok(s);
    nodes.set(id, { id, lifecycle: s.lifecycle, signature: s.structural_sig });
    if (s.lifecycle === 'ADMITTED') return;
    const e = parent.get(id); assert.ok(e);
    for (const input of e.inputs) visit(input);
    events.set(e.id, e);
  }
  visit(target);
  return { nodes: [...nodes.values()], events: [...events.values()].sort((a,b) => a.level-b.level) };
}
const claim = structuralSignature(archive.node);
const product = payload.structures.find(s => s.structural_hash === structuralHash(claim));
assert.ok(product, 'the exact archived scalar PRODUCT signature must regenerate');
const integer = payload.structures.find(s => s.structural_hash === structuralHash({ ...claim, kind: 'INTEGER' }));
assert.ok(integer);
assert.ok(payload.structures.every(s => !Object.hasOwn(s.structural_sig, 'formula')));
console.log(JSON.stringify({
  case: 'archived-4d-quantum-hall-node-331', grammar_hash: payload.grammar_hash,
  formula_source_file_sha256: sha256(readFileSync(new URL('../site/physics-cards.js', import.meta.url), 'utf8')),
  archive: { ref: archive.ref, path: archive.path, node_id: archive.node.id,
    verdict: archive.node.verdict, label: archive.node.label },
  current_generation: { states: payload.structures.length, applications: payload.derivation_events.length,
    validation: { clean: validation.clean, replayed: validation.integrity.replayed_derivation_events } },
  reproduced_scalar_claim: claim,
  product_trace: trace(product.id), integer_trace: trace(integer.id),
  displayed_formula: card.formula, displayed_formula_origin: card.formulaSource,
  formula_derivation_status: 'NOT_ESTABLISHED_BY_THIS_AUDIT',
  missing_proof_obligations: [
    'Construct the mathematical realization of the generated carrier and its admissible maps.',
    'Construct and compute a characteristic invariant with explicit assumptions, normalization and proof.',
    'Derive a response relation and specify how its quantities correspond to measurements.',
    'Test a frozen independent case and counterexamples without fitting the generator to the answer.'
  ],
  limits: [
    'This regenerates matching scalar states under the current kernel; it does not recover the original Run 34 operator history.',
    'A valid structural trace does not alone compute a Chern invariant or a Hall response.',
    'Absence of a formula field is not proof that no invariant can be reconstructed from generated relations.',
    'The archive verdict is preserved; this audit neither manufactures a native DIRECT verdict nor changes a catalog match.'
  ]
}, null, 2));
