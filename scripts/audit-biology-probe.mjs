// External probe only. Neither candidates nor their projections enter generation.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { normalizeStructuralClaim, structuralHash, trueConfluences, sha256 } from '../science/core.mjs';
import { validateGenerationPayload } from '../science/validation.mjs';

const probeBytes = readFileSync(new URL('../audit/biology-cell-division-probe.json', import.meta.url), 'utf8');
const probe = JSON.parse(probeBytes);
const payload = JSON.parse(execFileSync('python3', [fileURLToPath(new URL('./science-generate.py', import.meta.url)),
  '--generation-id', probe.id, '--levels', '5', '--cap', '20000'], { maxBuffer: 32 * 1024 * 1024, encoding: 'utf8' }));
const validation = validateGenerationPayload({ id: payload.generation_id, grammar_hash: payload.grammar_hash,
  maxdim: payload.experiment.maxdim, expansion_levels: payload.experiment.levels,
  node_count: payload.structures.length, derivation_event_count: payload.derivation_events.length,
  true_confluence_count: trueConfluences(payload.derivation_events).length }, payload.structures, payload.derivation_events);
assert.equal(validation.clean, true, validation.errors.join('\n'));
const byId = new Map(payload.structures.map(s => [s.id, s]));
// Earliest seed-rooted derivations. ALL inputs must already be established.
const reached = new Set(payload.structures.filter(s => s.lifecycle === 'ADMITTED').map(s => s.id));
const parent = new Map();
for (const event of payload.derivation_events) {
  if (!reached.has(event.output) && event.inputs.every(id => reached.has(id))) {
    reached.add(event.output); parent.set(event.output, event);
  }
}
function trace(id) {
  const nodes = new Map(), events = new Map();
  function visit(current) {
    if (nodes.has(current)) return;
    const s = byId.get(current);
    assert.ok(s); nodes.set(current, { id: s.id, lifecycle: s.lifecycle, signature: s.structural_sig });
    if (s.lifecycle === 'ADMITTED') return;
    const e = parent.get(current); assert.ok(e, 'trace must reach admitted seeds');
    for (const input of e.inputs) visit(input);
    events.set(e.id, e);
  }
  visit(id);
  return { nodes: [...nodes.values()], events: [...events.values()].sort((a,b) => a.level-b.level),
    status: 'SEED_ROOTED_STRUCTURAL_TRACE_ONLY' };
}
const projections = probe.projections.map((p, i) => {
  const signature = normalizeStructuralClaim(p.claim), hash = structuralHash(signature);
  const hits = payload.structures.filter(s => s.structural_hash === hash);
  return { name: p.name, signature, matches: hits.map(s => ({ id: s.id, trace: trace(s.id) })),
    control_same_signature: hash === structuralHash(probe.negative_control.projections[i]) };
});
const relaxed = payload.structures.filter(s => Object.entries(probe.relaxed_query)
  .every(([k,v]) => s.structural_sig[k] === v));
const fullClaim = { ...probe.projections[0].claim,
  genetic_information: 'copied and inherited', phase_order: ['replication', 'segregation', 'division'],
  daughter_cells: 2 };
let schemaError = null;
try { normalizeStructuralClaim(fullClaim); } catch (e) { schemaError = e.message; }
assert.ok(schemaError);
assert.ok(projections.every(p => p.control_same_signature));
console.log(JSON.stringify({ probe_id: probe.id, probe_sha256: sha256(probeBytes),
  grammar_hash: payload.grammar_hash, experiment: payload.experiment,
  counts: { structures: payload.structures.length, events: payload.derivation_events.length },
  validation: { clean: validation.clean, errors: validation.errors, counts: validation.counts,
    integrity: validation.integrity },
  projections, relaxed_multiplicity_query: { query: probe.relaxed_query,
    warning: 'Partial query ignores symmetry; it is not an exact biological match.',
    matches: relaxed.map(s => ({ id: s.id, trace: trace(s.id) })) },
  full_claim_normalization_error: schemaError,
  biology_direct: false, verdict: 'BIOLOGICAL_MECHANISM_NOT_ESTABLISHED',
  limitations: ['Manual projections are hypotheses, not independent adjudicated normalizations.',
    'Multiplicity is not a daughter-cell count without a justified semantic bridge.',
    'op_degenerate explicitly assigns multiplicity two for its anti/sq=-1 seed.',
    'Schema rejection concerns this serialization; it does not prove biology cannot emerge from relations.',
    'No reconstruction of genetic copying, inheritance or cell partition was implemented or demonstrated.',
    'No database writes, production interpretations, external LLM calls or native DIRECT verdict.']
}, null, 2));
