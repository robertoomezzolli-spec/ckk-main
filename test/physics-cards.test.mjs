import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';

import { STATUS_INFO, buildPhysicsCardModel, renderPhysicsCard, renderStatusGlossary } from '../site/physics-cards.js';

const base = { recurrence_order: 0, symmetry: null, multiplicity: 1, boundary_condition: null, occupancy: null, lifecycle: 'GENERABLE' };
const cycle = { ...base, id: '76', kind: 'CYCLE', dim: 1, dual: 0, depth: 1, paths: 6, verdict: 'KNOWN', label: 'Euclidean time / U(1) phase', signature: { snapshot_node: { factor: '2pi', phys: ['U(1)-Phase'] } } };
const known = { ...base, id: '151', kind: 'INTEGER', dim: 1, dual: 0, depth: 2, paths: 34, verdict: 'KNOWN', label: 'Bohr–Sommerfeld / Flux Quantization / Josephson / Double Slit', signature: { snapshot_node: { factor: '2pi', phys: ['Bohr-Sommerfeld', 'Flussquantisierung', 'Superfluid-Zirkulation', 'Teilchen im Ring', 'Josephson', 'Doppelspalt'] } } };
const unmatched = { ...base, id: '316', kind: 'PRODUCT', dim: 3, dual: 0, depth: 2, paths: 266, verdict: 'UNMATCHED', label: 'gravity', signature: { snapshot_node: { factor: '2pi', phys: [] } } };
const rediscovered = { ...base, id: '331', kind: 'PRODUCT', dim: 4, dual: 0, depth: 2, paths: 260, verdict: 'REDISCOVERED', label: '4D quantum Hall / second Chern number', signature: { snapshot_node: { factor: '2pi', phys: ['4D-QHE / zweite Chernzahl'] } } };
const originalBundle = { ...base, id: '32', kind: 'BUNDLE', dim: 1, dual: 0, depth: 2, paths: 120, verdict: 'KNOWN', label: 'Aharonov–Bohm bundle', signature: { snapshot_node: { factor: '2pi', phys: ['Aharonov-Bohm-Buendel'] } } };
const dualBundle = { ...base, id: '33', kind: 'BUNDLE', dim: 1, dual: 1, depth: 3, paths: 17, verdict: 'VARIANT', label: 'Aharonov–Bohm variant', signature: { snapshot_node: { factor: '2pi', phys: [] } } };
const graph = {
  nodes: [cycle, known, unmatched, rediscovered, originalBundle, dualBundle],
  edges: [
    { source_id: '76', target_id: '151', operator: 'snapshot_v6:0002', paths: 2 },
    { source_id: '76', target_id: '316', operator: 'snapshot_v6:0003', paths: 2 },
    { source_id: '316', target_id: '331', operator: 'snapshot_v6:0004', paths: 2 },
    { source_id: '32', target_id: '33', operator: 'snapshot_v6:0005', paths: 2 },
  ],
  duality_clusters: [],
  methodology: { self_duality: { assessment: 'NOT_EVALUATED', equivalence_relation: null } },
};

test('known integer card leads with physical meaning, formula, and all six realizations', () => {
  const model = buildPhysicsCardModel(known, graph); const html = renderPhysicsCard(known, graph);
  assert.equal(model.formula, '1/(2π) ∮ᴄ dφ = n,    n ∈ ℤ');
  assert.deepEqual(model.realizations, ['Bohr–Sommerfeld', 'Flux quantization', 'Superfluid circulation', 'Particle on a ring', 'Josephson', 'Double slit']);
  assert.match(html, /PHYSICS ANNOTATION/); assert.match(html, /CYCLE → INTEGER/);
  assert.match(html, /Winding \/ closure count · compatible/);
  assert.match(html, /does not retain its original operator label/);
  assert.match(html, /It did not determine the generated topology/);
});

test('unmatched card stays attractive without allowing its label to become evidence', () => {
  const model = buildPhysicsCardModel(unmatched, graph); const html = renderPhysicsCard(unmatched, graph);
  assert.equal(model.title, 'UNMATCHED STRUCTURE'); assert.equal(model.formulaSource, 'GENERATED STRUCTURE');
  assert.equal(model.formula, 'X = PRODUCT[d=3](2π, m=1, dual=original)');
  assert.doesNotMatch(html, /gravity/); assert.match(html, /Catalog match<\/span><strong>NONE/);
  assert.match(html, /Generated independently of catalog labels<\/span><strong>YES/);
  assert.match(html, /Path multiplicity alone does not prove independent seed families/);
});

test('rediscovered card separates its catalog formula from generated structure', () => {
  const html = renderPhysicsCard(rediscovered, graph);
  assert.match(html, /REDISCOVERED/); assert.match(html, /C₂ = 1\/\(8π²\) ∫M₄ Tr\(F ∧ F\) ∈ ℤ/);
  assert.match(html, /This formula describes the catalog interpretation/);
  assert.match(html, /4D quantum Hall \/ second Chern number/);
});

test('dual transformed card resolves a partner without asserting self-duality', () => {
  const model = buildPhysicsCardModel(dualBundle, graph); const html = renderPhysicsCard(dualBundle, graph);
  assert.equal(model.partner.id, '32'); assert.match(html, /Dual transformed/); assert.match(html, /X★ = D\(X\)/);
  assert.match(html, /data-node-id="32"/); assert.match(html, /D\(D\(X\)\) = X/);
  assert.match(html, /NOT_EVALUATED/); assert.match(html, /No self-duality claim is made/); assert.doesNotMatch(html, /DUAL 1/);
});

test('status definitions and raw technical signature are always available', () => {
  const html = renderPhysicsCard(unmatched, graph); const glossary = renderStatusGlossary();
  assert.match(html, /<details class="technical-signature">/); assert.match(html, /operator_depth/);
  for (const [status, explanation] of Object.entries(STATUS_INFO)) { assert.ok(glossary.includes(status)); assert.ok(glossary.includes(explanation)); }
});

test('application wires card navigation, path focus, and graph reset', async () => {
  const source = await fs.readFile(new URL('../site/app.js', import.meta.url), 'utf8');
  assert.match(source, /querySelectorAll\('\.node-link'\)/); assert.match(source, /querySelectorAll\('\.path-link'\)/);
  assert.match(source, /data-reset-graph/); assert.match(source, /focusPath/);
});
