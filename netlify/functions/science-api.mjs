import { deterministicId, normalizeStructuralClaim, sha256 } from '../../science/core.mjs';
import { ScienceStore } from './_science_store.mjs';

function response(payload, status = 200) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      'x-ckk-plane': 'scientific',
    },
  });
}

function routeFor(request) {
  const url = new URL(request.url);
  const explicit = url.searchParams.get('route');
  if (explicit != null) return explicit.replace(/^\/+|\/+$/g, '');
  const marker = '/science-api/';
  return url.pathname.includes(marker) ? url.pathname.split(marker)[1].replace(/^\/+|\/+$/g, '') : '';
}

function authorized(request, token) {
  if (!token) return false;
  return request.headers.get('authorization') === `Bearer ${token}`;
}

async function body(request) {
  try { return await request.json(); } catch { throw new Error('Request body must be valid JSON'); }
}

export async function handleScienceApi(request, overrides = {}) {
  const store = overrides.store ?? ScienceStore.connect(overrides.databaseUrl ?? process.env.DATABASE_URL);
  const route = routeFor(request);
  const parts = route.split('/').filter(Boolean);
  const method = request.method.toUpperCase();
  const writeToken = overrides.writeToken ?? process.env.SCIENCE_WRITE_TOKEN;

  try {
    if (method === 'GET' && route === 'overview') return response(await store.overview());
    if (method === 'GET' && route === 'generations') return response({ generations: await store.listGenerations() });
    if (method === 'GET' && parts[0] === 'generations' && parts.length === 2) {
      const result = await store.generation(parts[1]);
      return result ? response(result) : response({ error: 'Generation not found' }, 404);
    }
    if (method === 'GET' && route === 'candidates') return response({ candidates: await store.listCandidates() });
    if (method === 'GET' && parts[0] === 'candidates' && parts.length === 2) {
      const result = await store.candidate(parts[1]);
      return result ? response(result) : response({ error: 'Candidate not found' }, 404);
    }
    if (method === 'GET' && route === 'disputes') return response({ disputes: await store.disputes() });
    if (method === 'GET' && route === 'failures') return response({ failures: await store.failures() });
    if (method === 'GET' && route === 'grammar-pressure') return response(await store.grammarPressure());
    if (method === 'GET' && route === 'cross-domain') return response({ matches: await store.crossDomain() });
    if (method === 'GET' && parts[0] === 'structures' && parts.length === 2) {
      const generationId = new URL(request.url).searchParams.get('generation');
      const result = await store.structure(parts[1], generationId);
      return result ? response(result) : response({ error: 'Structure not found' }, 404);
    }

    if (method !== 'GET' && !authorized(request, writeToken)) {
      return response({ error: 'Scientific writes require a preview-scoped bearer token' }, 401);
    }

    if (method === 'POST' && route === 'candidates') {
      const input = await body(request);
      if (!input.domain || !input.name || !input.dedupe_key) return response({ error: 'domain, name and dedupe_key are required' }, 400);
      return response(await store.createCandidate({ ...input, created_by_agent: input.created_by_agent ?? 'SCIENCE_API' }), 201);
    }
    if (method === 'POST' && route === 'normalizations') {
      const input = await body(request);
      const structuralClaim = normalizeStructuralClaim(input.structural_claim);
      const inputHash = input.input_hash ?? sha256({ candidate_id: input.candidate_id, evidence: input.input_evidence_ids });
      const outputHash = sha256(structuralClaim);
      const id = input.id ?? deterministicId('norm', { candidate_id: input.candidate_id, agent_role: input.agent_role, inputHash, outputHash });
      return response(await store.addNormalization({ ...input, id, structural_claim: structuralClaim, input_hash: inputHash, output_hash: outputHash }), 201);
    }
    if (method === 'POST' && route === 'adjudications') {
      const input = await body(request);
      return response(await store.adjudicate(input.candidate_id, input, input.judge_version ?? 'science-api-v1'), 201);
    }
    if (method === 'POST' && parts[0] === 'generations' && parts[2] === 'validate') {
      const report = await store.validateGeneration(parts[1]);
      return response(report, report.clean ? 200 : 422);
    }
    if (method === 'POST' && parts[0] === 'generations' && parts[2] === 'seal') {
      const input = await body(request);
      if (input.public_eligible === true) return response({ error: 'Public eligibility requires explicit production GO and is forbidden in preview API' }, 403);
      return response(await store.sealGeneration(parts[1], { publicEligible: false, candidateId: input.candidate_id ?? null }), 201);
    }
    return response({ error: 'Route not found', route, method }, 404);
  } catch (error) {
    return response({ error: String(error.message ?? error), route, method }, 500);
  }
}

export default handleScienceApi;

