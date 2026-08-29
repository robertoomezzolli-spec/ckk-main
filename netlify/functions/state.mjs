import { neon } from '@neondatabase/serverless';
import { readLegacySnapshot } from './_legacy_snapshot.mjs';

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'public,max-age=0,s-maxage=15',
      'x-ckk-source': 'neon',
    },
  });
}

export async function handleState(_request, overrides = {}) {
  const now = (overrides.now ?? (() => new Date().toISOString()))();
  const databaseUrl = overrides.databaseUrl ?? process.env.DATABASE_URL;
  if (!databaseUrl) {
    return json({
      nodes: [], edges: [], duality_clusters: [], probes: [], run: null,
      events: [], queue: [], evidence: [], now, error: 'DATABASE_URL missing',
    }, 503);
  }

  try {
    const connect = overrides.connect ?? neon;
    const readSnapshot = overrides.readSnapshot ?? readLegacySnapshot;
    const snapshot = await readSnapshot(connect(databaseUrl));
    return json({
      nodes: snapshot.nodes,
      edges: snapshot.edges,
      duality_clusters: snapshot.duality_clusters,
      probes: snapshot.probes,
      probe_resolution: snapshot.probe_resolution,
      run: snapshot.run,
      events: snapshot.events,
      queue: snapshot.queue,
      evidence: snapshot.evidence,
      physics_catalog: snapshot.physics_catalog,
      methodology: snapshot.methodology,
      generation_id: snapshot.generation_id,
      now,
    });
  } catch (error) {
    return json({
      nodes: [], edges: [], duality_clusters: [], probes: [], run: null,
      events: [{ id: 0, created_at: now, event_type: 'ERROR', summary: String(error), payload: {} }],
      queue: [], evidence: [], now,
    }, 500);
  }
}

export default handleState;
