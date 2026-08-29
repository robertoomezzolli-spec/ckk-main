import assert from 'node:assert/strict';
import { test } from 'node:test';
import { handlePublicApi } from '../netlify/functions/public-api.mjs';
import { handleScienceApi } from '../netlify/functions/science-api.mjs';

const overview = { schema: 'ckk.science-overview.v1', separation: { structure_derivation_interpretation: true } };

function scienceStore() {
  return {
    overview: async () => overview,
    listGenerations: async () => [{ id: 'g', status: 'SEALED' }],
    generation: async (id) => id === 'g' ? { generation: { id, status: 'SEALED' }, structures: [], derivation_events: [] } : null,
    listCandidates: async () => [{ id: 'c' }],
    candidate: async (id) => id === 'c' ? { candidate: { id } } : null,
    disputes: async () => [], failures: async () => [], grammarPressure: async () => ({ groups: [], proposals: [] }), crossDomain: async () => [],
    structure: async (id) => ({ structure: { id } }),
    createCandidate: async (input) => ({ id: 'created', ...input }),
    addNormalization: async (input) => input,
    adjudicate: async () => ({ verdict: 'ACCEPT_NORMALIZATION' }),
    validateGeneration: async () => ({ clean: true }),
    sealGeneration: async () => ({ seal: { public_eligible: false } }),
  };
}

test('science overview and generation inspector are read-only routes', async () => {
  const store = scienceStore();
  const response = await handleScienceApi(new Request('https://example.test/api/science/overview?route=overview'), { store });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), overview);
  const generation = await handleScienceApi(new Request('https://example.test/api/science/generations/g?route=generations/g'), { store });
  assert.equal((await generation.json()).generation.id, 'g');
});

test('Netlify path-based function rewrite preserves the scientific route', async () => {
  const store = scienceStore();
  const response = await handleScienceApi(new Request('https://example.test/.netlify/functions/science-api/overview'), { store });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).schema, 'ckk.science-overview.v1');
});

test('science writes require a preview-scoped token and public eligibility is forbidden', async () => {
  const store = scienceStore();
  const unauthorized = await handleScienceApi(new Request('https://example.test/api/science/candidates?route=candidates', { method: 'POST', body: '{}', headers: { 'content-type': 'application/json' } }), { store, writeToken: 'secret' });
  assert.equal(unauthorized.status, 401);
  const seal = await handleScienceApi(new Request('https://example.test/api/science/generations/g/seal?route=generations/g/seal', {
    method: 'POST', headers: { authorization: 'Bearer secret', 'content-type': 'application/json' }, body: JSON.stringify({ public_eligible: true }),
  }), { store, writeToken: 'secret' });
  assert.equal(seal.status, 403);
});

test('public API exposes only the store sealed projection and rejects writes', async () => {
  const store = {
    publicActiveGeneration: async () => ({ id: 'sealed', status: 'SEALED', public_eligible: true }),
    publicUniverse: async () => ({ generation: { id: 'sealed' } }),
    publicStructure: async (id) => ({ structure: { id } }),
    publicCrossDomain: async (hash) => ({ structural_hash: hash, verdict: 'STRUCTURAL_MATCH', same_mechanism: 'NOT_EVALUATED' }),
  };
  const active = await handlePublicApi(new Request('https://example.test/api/public/generations/active?route=generations/active'), { store });
  assert.equal((await active.json()).id, 'sealed');
  const write = await handlePublicApi(new Request('https://example.test/api/public/universe?route=universe', { method: 'POST' }), { store });
  assert.equal(write.status, 405);
  const rewritten = await handlePublicApi(new Request('https://example.test/.netlify/functions/public-api/generations/active'), { store });
  assert.equal((await rewritten.json()).id, 'sealed');
});
