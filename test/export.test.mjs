import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';
import { gunzipSync } from 'node:zlib';

import { readLegacySnapshot } from '../netlify/functions/_legacy_snapshot.mjs';
import { createExportResponse, handleExport } from '../netlify/functions/export-graph.mjs';

const SOURCE_HASH = 'a'.repeat(64);
const EXPORTED_AT = '2026-08-27T12:30:00.000Z';

function queryText(query) {
  return query.strings.join('?');
}

async function snapshotFixture() {
  const calls = [];
  function sql(strings, ...values) {
    return { strings: [...strings], values };
  }
  sql.transaction = async (queries, options) => {
    calls.push({ queries, options });
    return [
      [{
        id: 7,
        grammar_version: 'v6-html-snapshot',
        source_commit: SOURCE_HASH,
        node_count: 2,
        edge_count: 1,
        unmatched_count: 1,
      }],
      [
        {
          id: '0', kind: 'RECURRENCE', dim: 0, recurrence_order: 0,
          symmetry: null, multiplicity: 1, boundary_condition: null,
          dual: 0, occupancy: null, lifecycle: 'ADMITTED', verdict: 'UNMATCHED',
          paths: 1, depth: 0, label: null,
          signature: { source: 'ckk_faecher.html', snapshot_node: { factor: '—' } },
        },
        {
          id: '1', kind: 'CYCLE', dim: 1, recurrence_order: 0,
          symmetry: null, multiplicity: 1, boundary_condition: null,
          dual: 0, occupancy: null, lifecycle: 'GENERABLE', verdict: 'KNOWN',
          paths: 1, depth: 1, label: 'U(1)',
          signature: { source: 'ckk_faecher.html', snapshot_node: { factor: '2pi' } },
        },
      ],
      [{ id: 1, source_id: '0', target_id: '1', operator: 'snapshot_v6:0000', paths: 1 }],
      [],
      [],
      [],
    ];
  };
  return { snapshot: await readLegacySnapshot(sql), calls };
}

test('legacy export reader uses one read-only repeatable-read transaction', async () => {
  const { snapshot, calls } = await snapshotFixture();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.isolationLevel, 'RepeatableRead');
  assert.equal(calls[0].options.readOnly, true);
  assert.ok(calls[0].queries.every((query) => /^SELECT\b/i.test(queryText(query).trim())));
  assert.equal(snapshot.generation_id, 'v6-html-aaaaaaaaaaaa');
  assert.equal(snapshot.run.node_count, 2);
  assert.equal(snapshot.validation.clean, true);
  assert.equal(snapshot.validation.unverified_selfduality_claims, 0);
  assert.equal(snapshot.methodology.self_duality.assessment, 'NOT_EVALUATED');
  assert.equal(snapshot.methodology.self_duality.equivalence_relation, null);
  assert.equal(snapshot.methodology.visualization.depth_implies_dimension, false);
  assert.equal(snapshot.nodes[1].signature.snapshot_node.factor, '2pi');
});

test('JSON and gzip downloads contain the same complete sealed snapshot', async () => {
  const { snapshot } = await snapshotFixture();
  const jsonResponse = await createExportResponse(
    new Request('https://ckk-live.netlify.app/.netlify/functions/export-graph?format=json'),
    snapshot,
    EXPORTED_AT,
  );
  assert.equal(jsonResponse.status, 200);
  assert.equal(jsonResponse.headers.get('content-type'), 'application/json; charset=utf-8');
  assert.equal(
    jsonResponse.headers.get('content-disposition'),
    'attachment; filename="ckk-graph-v6-html-aaaaaaaaaaaa.json"',
  );
  const jsonPayload = await jsonResponse.json();

  const gzipResponse = await createExportResponse(
    new Request('https://ckk-live.netlify.app/.netlify/functions/export-graph?format=json.gz'),
    snapshot,
    EXPORTED_AT,
  );
  assert.equal(gzipResponse.headers.get('content-type'), 'application/gzip');
  assert.equal(gzipResponse.headers.get('content-encoding'), null);
  const gzipPayload = JSON.parse(gunzipSync(Buffer.from(await gzipResponse.arrayBuffer())).toString('utf8'));

  assert.deepEqual(gzipPayload, jsonPayload);
  assert.equal(jsonPayload.generation_id, snapshot.generation_id);
  assert.equal(jsonPayload.nodes.length, 2);
  assert.equal(jsonPayload.edges.length, 1);
  assert.equal(jsonPayload.run.node_count, jsonPayload.nodes.length);
  assert.equal(jsonPayload.run.edge_count, jsonPayload.edges.length);
  assert.equal(jsonPayload.validation.dangling_edges, 0);
  assert.ok(Object.hasOwn(jsonPayload, 'probe_resolution'));
  assert.ok(Object.hasOwn(jsonPayload, 'physics_catalog'));
  assert.equal(jsonPayload.methodology.self_duality.assessment, 'NOT_EVALUATED');
  assert.equal(jsonPayload.nodes[1].signature.snapshot_node.factor, '2pi');
});

test('default summary is compact and manifest advertises all modes', async () => {
  const { snapshot } = await snapshotFixture();
  const deps = {
    databaseUrl: 'postgresql://test.invalid/ckk',
    connect: () => ({}),
    readSnapshot: async () => snapshot,
    now: () => EXPORTED_AT,
  };
  const summaryResponse = await handleExport(
    new Request('https://ckk-live.netlify.app/.netlify/functions/export-graph'),
    deps,
  );
  const summary = await summaryResponse.json();
  assert.equal(summary.summary.structures, 2);
  assert.equal(summary.nodes, undefined);

  const manifestResponse = await handleExport(
    new Request('https://ckk-live.netlify.app/.netlify/functions/export-graph?format=manifest'),
    deps,
  );
  const manifest = await manifestResponse.json();
  assert.equal(manifest.generation_id, snapshot.generation_id);
  assert.deepEqual(
    manifest.available_exports.map((item) => item.format),
    ['summary', 'manifest', 'graph', 'full', 'json', 'json.gz'],
  );
});

test('export implementation is observational and UI downloads files directly', async () => {
  for (const file of ['_legacy_snapshot.mjs', 'export-graph.mjs']) {
    const source = await fs.readFile(new URL(`../netlify/functions/${file}`, import.meta.url), 'utf8');
    assert.doesNotMatch(source, /\b(?:DELETE|INSERT|UPDATE|persist|publishGraph|rebuild)\b/i);
  }
  const html = await fs.readFile(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.match(html, /export-graph\?format=json" download>Export JSON<\/a>/);
  assert.match(html, /export-graph\?format=json\.gz" download>Export gzip<\/a>/);
  assert.doesNotMatch(html, /export-graph[^>]+target=/);
});

test('unsupported format is rejected before reading the database', async () => {
  let reads = 0;
  const response = await handleExport(
    new Request('https://ckk-live.netlify.app/.netlify/functions/export-graph?format=csv'),
    {
      databaseUrl: 'postgresql://test.invalid/ckk',
      connect: () => ({}),
      readSnapshot: async () => { reads += 1; },
    },
  );
  assert.equal(response.status, 400);
  assert.equal(reads, 0);
});
