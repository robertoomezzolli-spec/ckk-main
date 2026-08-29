import { ScienceStore } from './_science_store.mjs';

function response(payload, status = 200) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'public,max-age=0,s-maxage=15',
      'x-content-type-options': 'nosniff',
      'x-ckk-plane': 'public-sealed-only',
    },
  });
}

function routeFor(request) {
  const url = new URL(request.url);
  const explicit = url.searchParams.get('route');
  if (explicit != null) return explicit.replace(/^\/+|\/+$/g, '');
  const marker = '/public-api/';
  return url.pathname.includes(marker) ? url.pathname.split(marker)[1].replace(/^\/+|\/+$/g, '') : '';
}

export async function handlePublicApi(request, overrides = {}) {
  if (request.method !== 'GET') return response({ error: 'Public API is read-only' }, 405);
  const store = overrides.store ?? ScienceStore.connect(overrides.databaseUrl ?? process.env.DATABASE_URL);
  const route = routeFor(request);
  const parts = route.split('/').filter(Boolean);
  try {
    if (route === 'generations/active') {
      const active = await store.publicActiveGeneration();
      return active ? response(active) : response({ active_generation_id: null, reason: 'NO_PUBLIC_ELIGIBLE_SEALED_SCIENTIFIC_GENERATION' }, 404);
    }
    if (route === 'universe') {
      const universe = await store.publicUniverse();
      return universe ? response(universe) : response({ error: 'No public eligible sealed Scientific generation' }, 404);
    }
    if (parts[0] === 'structures' && parts.length === 2) {
      const structure = await store.publicStructure(parts[1]);
      return structure ? response(structure) : response({ error: 'Structure not found in active sealed generation' }, 404);
    }
    if (parts[0] === 'cross-domain' && parts.length === 2) {
      const match = await store.publicCrossDomain(parts[1]);
      return match ? response(match) : response({ error: 'No active sealed generation' }, 404);
    }
    return response({ error: 'Route not found', route }, 404);
  } catch (error) {
    return response({ error: String(error.message ?? error) }, 500);
  }
}

export default handlePublicApi;
