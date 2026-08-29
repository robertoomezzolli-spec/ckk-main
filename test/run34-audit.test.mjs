import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  EXPECTED_RUN34,
  compactSignature,
  semanticRiskForParents,
} from '../scripts/run34-audit.mjs';

const report = JSON.parse(await readFile(new URL('../audit/run34-audit.json', import.meta.url), 'utf8'));

test('Run 34 hard-integrity results are independently sealed', () => {
  assert.equal(report.hard_integrity.status, 'PASS');
  assert.deepEqual(
    {
      generation_id: report.source.generation_id,
      grammar_version: report.source.grammar_version,
      run_id: report.source.run_id,
      nodes: report.hard_integrity.measured.nodes,
      edges: report.hard_integrity.measured.edges,
      confluences: report.hard_integrity.measured.confluences_by_indegree_gte_2,
    },
    {
      generation_id: EXPECTED_RUN34.generation_id,
      grammar_version: EXPECTED_RUN34.grammar_version,
      run_id: EXPECTED_RUN34.run_id,
      nodes: EXPECTED_RUN34.nodes,
      edges: EXPECTED_RUN34.edges,
      confluences: EXPECTED_RUN34.confluences,
    },
  );
  assert.equal(report.source.sha256, '8627e79c0b7ef61a2d989290c2250003f837590d37cb2c99fa9c31d008335a90');
  assert.equal(report.hard_integrity.measured.dangling_edges, 0);
  assert.equal(report.hard_integrity.measured.self_loops, 0);
  assert.equal(report.hard_integrity.measured.duplicate_node_ids, 0);
  assert.equal(report.hard_integrity.measured.unverified_selfduality_claims, 0);
});

test('all 276 node audit records contain the required structural fields', () => {
  const required = [
    'id', 'kind', 'dim', 'depth', 'verdict', 'lifecycle', 'factor', 'symmetry',
    'multiplicity', 'boundary_condition', 'occupancy', 'dual', 'paths', 'indegree',
    'outdegree', 'unique_parents', 'unique_children', 'root_classes', 'root_diversity',
    'catalog_match', 'confluence', 'provenance_quality', 'semantic_risk',
  ];
  assert.equal(report.nodes.length, 276);
  for (const node of report.nodes) {
    for (const field of required) assert.ok(Object.hasOwn(node, field), `node ${node.id} missing ${field}`);
  }
});

test('root diversity uses only the six stored ADMITTED roots', () => {
  assert.deepEqual(report.root_diversity.root_class_definitions, {
    'CARRIER +1': ['11'],
    'CARRIER -1': ['12'],
    RECURRENCE: ['22'],
    SYMMETRY: ['23'],
    'BOUNDCOND D': ['8'],
    'BOUNDCOND N': ['9'],
  });
  const distributionTotal = Object.values(report.root_diversity.by_diversity).reduce((sum, value) => sum + value, 0);
  assert.equal(distributionTotal, 276);
});

test('semantic-risk rules do not read labels, verdicts, physics, or catalog data', () => {
  const structuralParents = [
    { kind: 'CYCLE', dim: 1, symmetry: null, boundary_condition: null, multiplicity: 1, dual: 0, signature: { snapshot_node: { factor: '2pi' } } },
    { kind: 'PRODUCT', dim: 2, symmetry: 'a', boundary_condition: 'D', multiplicity: 2, dual: 1, signature: { snapshot_node: { factor: 'pi' } } },
  ];
  const decoratedParents = structuralParents.map((parent, index) => ({
    ...parent,
    label: index ? 'gravity sphere flux' : 'Newton inverse square',
    verdict: index ? 'KNOWN' : 'REDISCOVERED',
    physics: [{ name: 'must not leak' }],
    catalog_match: true,
  }));
  assert.deepEqual(
    semanticRiskForParents(structuralParents, 4),
    semanticRiskForParents(decoratedParents, 4),
  );
});

test('confluences are exactly the independently measured indegree>=2 nodes', () => {
  const measured = report.nodes.filter((node) => node.indegree >= 2).map((node) => node.id).sort();
  const classified = report.confluences.all.map((node) => node.id).sort();
  assert.equal(measured.length, 196);
  assert.deepEqual(classified, measured);
  assert.equal(report.confluences.count, 196);
});

test('false-confluence ranking is structural and does not promote Node 316 by fiat', () => {
  assert.equal(report.methodology.labels_used_in_risk_or_ranking, false);
  assert.equal(report.methodology.physics_catalog_used_in_risk_or_ranking, false);
  assert.equal(report.unmatched.node_316_rank, 58);
  assert.notEqual(report.unmatched.top_candidates[0].id, '316');
  for (const candidate of report.confluences.top_25) {
    assert.ok(['LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK', 'REQUIRES_PROVENANCE'].includes(candidate.classification));
  }
});

test('Node 316 audit contains two levels and exact stored 257/331 relations', () => {
  const node316 = report.node_316;
  assert.deepEqual(
    {
      id: node316.stored_node.id,
      kind: node316.stored_node.kind,
      dim: node316.stored_node.dim,
      dual: node316.stored_node.dual,
      verdict: node316.stored_node.verdict,
      paths: node316.stored_node.paths,
    },
    { id: '316', kind: 'PRODUCT', dim: 3, dual: 0, verdict: 'UNMATCHED', paths: 266 },
  );
  assert.ok(node316.parents.level_1.nodes.length > 0);
  assert.ok(node316.parents.level_2.nodes.length > 0);
  assert.ok(node316.children.level_1.nodes.length > 0);
  assert.ok(node316.children.level_2.nodes.length > 0);
  assert.deepEqual(node316.relation_to_257.direct_edges.map((edge) => edge.id), ['7779']);
  assert.deepEqual(node316.relation_to_331.direct_edges.map((edge) => edge.id), ['8109']);
});

test('dimension chain reproduces stored snapshot identifiers without operator inference', () => {
  assert.deepEqual(report.dimension_chain.node_ids, ['22', '76', '257', '316', '331']);
  assert.deepEqual(
    report.dimension_chain.edges.map((entry) => ({
      pair: `${entry.source}->${entry.target}`,
      id: entry.stored_edges[0]?.id,
      operator: entry.stored_edges[0]?.operator,
      semantics: entry.operator_semantics,
    })),
    [
      { pair: '22->76', id: '7708', operator: 'snapshot_v6:0000', semantics: 'NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER' },
      { pair: '76->257', id: '7730', operator: 'snapshot_v6:0024', semantics: 'NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER' },
      { pair: '257->316', id: '7779', operator: 'snapshot_v6:0089', semantics: 'NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER' },
      { pair: '316->331', id: '8109', operator: 'snapshot_v6:0513', semantics: 'NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER' },
    ],
  );
});

test('dimension-transition matrix covers every d0..d4 pair and reports sparse d3->d4 coverage', () => {
  assert.equal(report.dimension_transitions.rows.length, 25);
  const d3d4 = report.dimension_transitions.rows.find((row) => row.transition === 'd3->d4');
  assert.deepEqual(
    {
      edge_count: d3d4.edge_count,
      unique_sources: d3d4.unique_sources,
      unique_targets: d3d4.unique_targets,
      source_coverage: d3d4.source_coverage,
      target_coverage: d3d4.target_coverage,
      average_fan_out: d3d4.average_fan_out,
      average_fan_in: d3d4.average_fan_in,
    },
    {
      edge_count: 1,
      unique_sources: 1,
      unique_targets: 1,
      source_coverage: 0.066667,
      target_coverage: 0.071429,
      average_fan_out: 1,
      average_fan_in: 1,
    },
  );
});

test('duality audit never upgrades signature pairing into involution or self-duality evidence', () => {
  assert.equal(report.duality.counts['1'], 68);
  assert.equal(report.duality.counts['2'] ?? 0, 0);
  assert.equal(report.duality.involution_assessment, 'NOT_VERIFIABLE_FROM_SNAPSHOT');
  assert.equal(report.duality.self_duality_assessment, 'NOT_EVALUATED');
  assert.equal(report.duality.rows.length, 68);
  for (const row of report.duality.rows) {
    assert.equal(row.involution_test, 'NOT_VERIFIABLE_FROM_SNAPSHOT');
    assert.equal(row.self_duality, 'NOT_EVALUATED');
    assert.deepEqual(row.semantic_op_dual_edges, []);
  }
});

test('provenance audit reports only what the projection actually stores', () => {
  assert.equal(report.provenance.semantic_operator_names, 0);
  assert.equal(report.provenance.snapshot_v6_identifiers, 945);
  assert.equal(report.provenance.no_usable_operator_provenance, 0);
  assert.match(report.provenance.methodological_limit, /cannot be reconstructed/);
});

test('KNOWN and REDISCOVERED controls are copied as stored claims only', () => {
  assert.equal(report.known_rediscovered_controls.known_count, 15);
  assert.equal(report.known_rediscovered_controls.rediscovered_count, 2);
  assert.equal(report.known_rediscovered_controls.highlighted_stored_claims.node_314.node_id, '314');
  assert.equal(report.known_rediscovered_controls.highlighted_stored_claims.node_331.node_id, '331');
  assert.match(report.known_rediscovered_controls.caveat, /no external physics validation/);
});

test('UNMATCHED analysis accounts for all 130 nodes', () => {
  assert.equal(report.unmatched.count, 130);
  assert.equal(
    Object.values(report.unmatched.by_dimension).reduce((sum, value) => sum + value, 0),
    130,
  );
  assert.equal(
    Object.values(report.unmatched.by_confluence).reduce((sum, value) => sum + value, 0),
    130,
  );
});

test('compact signature excludes labels and annotations', () => {
  const signature = compactSignature({
    kind: 'PRODUCT',
    dim: 3,
    recurrence_order: 0,
    symmetry: null,
    sq: null,
    anti: null,
    multiplicity: 1,
    boundary_condition: null,
    occupancy: null,
    dual: 0,
    label: 'ignored',
    physics: ['ignored'],
    signature: { snapshot_node: { factor: '2pi' } },
  });
  assert.equal(signature.factor, '2pi');
  assert.equal(Object.hasOwn(signature, 'label'), false);
  assert.equal(Object.hasOwn(signature, 'physics'), false);
});

test('change-safety seal keeps Run 34 and its generation unchanged', () => {
  assert.deepEqual(report.change_safety.before, report.change_safety.after);
  assert.equal(report.change_safety.graph_changed, false);
  assert.deepEqual(report.change_safety.before, {
    nodes: 276,
    edges: 945,
    run_id: '34',
    generation_id: 'v6-noselfdual-563f50e328c5',
  });
});
