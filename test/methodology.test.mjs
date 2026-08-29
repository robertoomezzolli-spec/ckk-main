import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs/promises';
import test from 'node:test';

import { analyzeConfluence, generate } from '../netlify/functions/_grammar.mjs';
import { handleState } from '../netlify/functions/state.mjs';
import {
  projectUnverifiedSelfduality,
  projectionDigest,
  validateProjection,
} from '../scripts/selfduality-projection.mjs';

test('JavaScript grammar cannot manufacture a self-duality assertion', () => {
  const graph = generate(2, 1200);
  assert.ok(graph.nodes.length > 0);
  assert.equal(graph.nodes.filter((node) => Number(node.dual) === 2).length, 0);
  assert.equal(graph.nodes.filter((node) => node.label === 'selfdual').length, 0);
});

test('Python grammar has no self-duality constructor and preserves Kramers condition', () => {
  const script = String.raw`
import grammar
from grammar import Struct, CYCLE, SYMMETRY

assert not hasattr(grammar, "op_selfdual")
assert all(op.__name__ != "op_selfdual" for op in grammar.UNARY)

base = Struct(CYCLE)
kramers = grammar.op_degenerate(
    base,
    Struct(SYMMETRY, label="neutral-test", sq=-1, anti=True),
)
non_kramers = grammar.op_degenerate(
    base,
    Struct(SYMMETRY, label="neutral-test", sq=1, anti=True),
)
not_antiunitary = grammar.op_degenerate(
    base,
    Struct(SYMMETRY, label="neutral-test", sq=-1, anti=False),
)

assert kramers is not None and kramers.mult == 2
assert non_kramers is not None and non_kramers.mult == 1
assert not_antiunitary is None
`;
  const result = spawnSync('python3', ['-c', script], {
    cwd: new URL('../ckk_snapshot/ckk/gen/', import.meta.url),
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});

test('UI names operator depth and structural dimension separately', async () => {
  const source = await fs.readFile(new URL('../site/app.js', import.meta.url), 'utf8');
  const cards = await fs.readFile(new URL('../site/physics-cards.js', import.meta.url), 'utf8');
  assert.match(source, /DEPTH \$\{depth\}/);
  assert.match(source, /vertical axis = operator depth/);
  assert.match(source, /structural dimension/);
  assert.match(cards, /operator_depth/);
  assert.match(cards, /dimension/);
  assert.doesNotMatch(source, />L\$\{dep\}<\/text>/);
});

test('state endpoint is observational and delegates to one sealed snapshot reader', async () => {
  const source = await fs.readFile(new URL('../netlify/functions/state.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /\b(?:DELETE|INSERT|UPDATE|persist|publishGraph|rebuild)\b/i);

  let reads = 0;
  const snapshot = {
    nodes: [{ id: 'a', dim: 1, depth: 3 }],
    edges: [],
    duality_clusters: [],
    probes: [],
    probe_resolution: {},
    run: { id: 1 },
    events: [],
    queue: [],
    evidence: [],
    physics_catalog: [],
    methodology: {
      self_duality: { assessment: 'NOT_EVALUATED' },
      visualization: { vertical_axis: 'operator_depth' },
    },
    generation_id: 'fixture-generation',
  };
  const response = await handleState(new Request('https://example.test/state'), {
    databaseUrl: 'postgresql://test.invalid/ckk',
    connect: () => ({}),
    readSnapshot: async () => { reads += 1; return snapshot; },
    now: () => '2026-08-27T14:00:00.000Z',
  });
  const payload = await response.json();
  assert.equal(reads, 1);
  assert.equal(payload.generation_id, 'fixture-generation');
  assert.equal(payload.nodes[0].dim, 1);
  assert.equal(payload.nodes[0].depth, 3);
  assert.equal(payload.methodology.self_duality.assessment, 'NOT_EVALUATED');
});

test('sealed projection removes only asserted dual=2 nodes and all incident edges', () => {
  const nodes = [
    { id: 'seed', dual: 0 },
    { id: 'asserted', dual: 2 },
    { id: 'survivor', dual: 1 },
  ];
  const edges = [
    { source_id: 'seed', target_id: 'asserted', operator: 'claim', paths: 1 },
    { source_id: 'asserted', target_id: 'survivor', operator: 'transport', paths: 1 },
    { source_id: 'seed', target_id: 'survivor', operator: 'dual', paths: 1 },
  ];
  const projection = projectUnverifiedSelfduality(nodes, edges);
  assert.deepEqual(projection.keptNodes.map((node) => node.id), ['seed', 'survivor']);
  assert.deepEqual(
    projection.keptEdges.map((edge) => [edge.source_id, edge.target_id]),
    [['seed', 'survivor']],
  );
  assert.deepEqual(validateProjection(projection), {
    asserted_selfduality_nodes: 0,
    dangling_edges: 0,
    self_loops: 0,
    duplicate_node_ids: 0,
  });
  assert.equal(projectionDigest('sealed-source', projection).length, 64);
  assert.equal(
    projectionDigest('sealed-source', projection),
    projectionDigest('sealed-source', projection),
  );
});

test('confluence analysis is deterministic under node and edge reordering with cycles', () => {
  const nodes = [
    { id: 'r', kind: 'RECURRENCE', dim: 0, recurrence_order: 0 },
    { id: 's', kind: 'SYMMETRY', dim: 0, recurrence_order: 0 },
    { id: 'a', kind: 'CYCLE', dim: 1, recurrence_order: 0 },
    { id: 'b', kind: 'CYCLE', dim: 1, recurrence_order: 0 },
    { id: 't', kind: 'PRODUCT', dim: 2, recurrence_order: 0 },
  ];
  const edges = [
    { source_id: 'r', target_id: 'a', operator: 'close' },
    { source_id: 's', target_id: 'b', operator: 'degenerate' },
    { source_id: 'a', target_id: 't', operator: 'product' },
    { source_id: 'b', target_id: 't', operator: 'product' },
    { source_id: 't', target_id: 'a', operator: 'cycle-backref' },
  ];
  const forward = analyzeConfluence(nodes, edges);
  const reversed = analyzeConfluence([...nodes].reverse(), [...edges].reverse());
  assert.deepEqual(reversed, forward);
  assert.equal(forward.some((cluster) => cluster.target_node_id === 't'), true);
});

test('an orphaned generated node is never promoted to an independent seed root', () => {
  const nodes = [
    { id: 'r', kind: 'RECURRENCE', dim: 0, recurrence_order: 0 },
    { id: 'a', kind: 'CYCLE', dim: 1, recurrence_order: 0 },
    { id: 'orphan', kind: 'CYCLE', dim: 1, recurrence_order: 0 },
    { id: 't', kind: 'PRODUCT', dim: 2, recurrence_order: 0 },
  ];
  const edges = [
    { source_id: 'r', target_id: 'a', operator: 'close' },
    { source_id: 'a', target_id: 't', operator: 'product' },
    { source_id: 'orphan', target_id: 't', operator: 'product' },
  ];
  assert.equal(analyzeConfluence(nodes, edges).length, 0);
});
