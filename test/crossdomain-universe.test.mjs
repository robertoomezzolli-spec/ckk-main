import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import {
  buildCrossDomainBridges,
  buildGraphIndex,
  DOMAINS,
  GOLDEN,
  nodeCardModel,
  structuralSignature,
  truthCounts,
  validateSnapshot,
} from '../site/src/model.js';

const snapshot = JSON.parse(await readFile(new URL('../site/public/data/run34.json', import.meta.url), 'utf8'));

test('sealed Run 34 payload validates independently', () => {
  const result = validateSnapshot(snapshot);
  assert.equal(result.clean, true, result.errors.join('\n'));
  assert.equal(snapshot.generation_id, GOLDEN.generationId);
  assert.equal(snapshot.nodes.length, 276);
  assert.equal(snapshot.edges.length, 945);
});

test('truth statuses are exactly the sealed Run 34 counts', () => {
  assert.deepEqual(truthCounts(snapshot.nodes), { UNMATCHED: 130, KNOWN: 15, VARIANT: 129, REDISCOVERED: 2 });
});

test('all four domain galaxies are declared without fabricating missing structures', () => {
  assert.deepEqual(Object.keys(DOMAINS), ['physics', 'chemistry', 'biology', 'computation']);
  assert.equal(DOMAINS.physics.structures, 276);
  for (const domain of ['chemistry', 'biology', 'computation']) {
    assert.equal(DOMAINS[domain].status, 'FOUND_PARTIAL');
    assert.equal(DOMAINS[domain].structures, 0);
    assert.equal(DOMAINS[domain].executable, false);
  }
});

test('production data has no certified cross-domain bridge', () => {
  const occurrences = snapshot.nodes.map((node) => ({ domain: 'physics', node }));
  assert.deepEqual(buildCrossDomainBridges(occurrences), []);
});

test('bridge engine reports structural match rather than semantic identity', () => {
  const node = snapshot.nodes[0];
  const bridges = buildCrossDomainBridges([{ domain: 'physics', node }, { domain: 'chemistry', node: { ...node, id: 'fixture-only' } }]);
  assert.equal(bridges.length, 1);
  assert.equal(bridges[0].status, 'STRUCTURAL_MATCH');
  assert.deepEqual(bridges[0].domains, ['physics', 'chemistry']);
  assert.deepEqual(bridges[0].signature, structuralSignature(node));
});

test('node cards distinguish legacy graph convergence from true derivational confluence', () => {
  const index = buildGraphIndex(snapshot);
  const model = nodeCardModel(index.nodes.get('316'), index);
  assert.equal(model.name, 'PRODUCT · d3');
  assert.equal(model.status, 'UNMATCHED');
  assert.equal(model.trueConfluence, 'NOT_VERIFIABLE_FROM_SNAPSHOT');
  assert.equal(model.provenance, 'REQUIRES_PROVENANCE');
  assert.ok(model.rootDiversity > 0);
});

test('self-duality is neither present in data nor inferred by model', () => {
  assert.equal(snapshot.nodes.some((node) => Number(node.dual) === 2), false);
  assert.equal(snapshot.methodology.self_duality.assessment, 'NOT_EVALUATED');
});

test('web app has no CDN runtime dependency', async () => {
  const html = await readFile(new URL('../site/index.html', import.meta.url), 'utf8');
  const css = await readFile(new URL('../site/src/style.css', import.meta.url), 'utf8');
  assert.doesNotMatch(html, /https?:\/\//);
  assert.doesNotMatch(css, /@import\s+url\(['"]?https?:\/\//);
  assert.match(html, /type="module" src="\/src\/main\.js"/);
});
