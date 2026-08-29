import { promisify } from 'node:util';
import { gzip } from 'node:zlib';
import { neon } from '@neondatabase/serverless';
import { readLegacySnapshot } from './_legacy_snapshot.mjs';

const FULL_SCHEMA = 'ckk.graph-export.v2';
const MANIFEST_SCHEMA = 'ckk.graph-export-manifest.v1';
const GRAPH_SCHEMA = 'ckk.graph-export-graph.v1';
const SUPPORTED_FORMATS = new Set(['summary', 'manifest', 'graph', 'full', 'json', 'json.gz']);
const gzipAsync = promisify(gzip);

function safeFilename(generationId, suffix) {
  const safeId = String(generationId || 'none').replace(/[^a-zA-Z0-9._-]/g, '_');
  return `ckk-graph-${safeId}.${suffix}`;
}

function formatUrl(request, format) {
  const url = new URL(request?.url || 'http://localhost/.netlify/functions/export-graph');
  url.search = '';
  url.searchParams.set('format', format);
  return url.toString();
}

function jsonResponse(payload, { status = 200, headers = {} } = {}) {
  const body = JSON.stringify(payload, null, 2);
  return new Response(body, {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'content-length': String(Buffer.byteLength(body)),
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      ...headers,
    },
  });
}

export function buildManifest(snapshot, request, exportedAt) {
  return {
    schema: MANIFEST_SCHEMA,
    exported_at: exportedAt,
    generation_id: snapshot.generation_id,
    grammar_version: snapshot.grammar_version,
    summary: snapshot.counts,
    validation: snapshot.validation,
    methodology: snapshot.methodology,
    available_exports: ['summary', 'manifest', 'graph', 'full', 'json', 'json.gz'].map((format) => ({
      format,
      url: formatUrl(request, format),
      content_type: format === 'json.gz' ? 'application/gzip' : 'application/json; charset=utf-8',
    })),
  };
}

export function buildSummary(snapshot) {
  return {
    run: snapshot.run,
    summary: snapshot.counts,
    validation: snapshot.validation,
    external_probes: snapshot.probes,
    probe_resolution: snapshot.probe_resolution,
    methodology: snapshot.methodology,
  };
}

export function buildGraph(snapshot, exportedAt) {
  return {
    schema: GRAPH_SCHEMA,
    exported_at: exportedAt,
    generation_id: snapshot.generation_id,
    grammar_version: snapshot.grammar_version,
    run: snapshot.run,
    nodes: snapshot.nodes,
    edges: snapshot.edges,
    methodology: snapshot.methodology,
  };
}

export function buildFull(snapshot, exportedAt) {
  return {
    schema: FULL_SCHEMA,
    exported_at: exportedAt,
    generation_id: snapshot.generation_id,
    grammar_version: snapshot.grammar_version,
    run: snapshot.run,
    summary: snapshot.counts,
    validation: snapshot.validation,
    nodes: snapshot.nodes,
    edges: snapshot.edges,
    duality_clusters: snapshot.duality_clusters,
    evidence: snapshot.evidence,
    events: snapshot.events,
    queue: snapshot.queue,
    external_probes: snapshot.probes,
    probe_resolution: snapshot.probe_resolution,
    physics_catalog: snapshot.physics_catalog,
    methodology: snapshot.methodology,
  };
}

export async function createExportResponse(request, snapshot, exportedAt = new Date().toISOString()) {
  const format = new URL(request?.url || 'http://localhost/.netlify/functions/export-graph')
    .searchParams.get('format') || 'summary';
  const generationHeader = snapshot.generation_id || 'none';

  if (format === 'summary') {
    return jsonResponse(buildSummary(snapshot), {
      headers: { 'x-ckk-generation': generationHeader },
    });
  }
  if (format === 'manifest') {
    return jsonResponse(buildManifest(snapshot, request, exportedAt), {
      headers: { 'x-ckk-generation': generationHeader },
    });
  }
  if (format === 'graph') {
    return jsonResponse(buildGraph(snapshot, exportedAt), {
      headers: { 'x-ckk-generation': generationHeader },
    });
  }

  const serialized = JSON.stringify(buildFull(snapshot, exportedAt), null, 2);
  if (format === 'full' || format === 'json') {
    return new Response(serialized, {
      headers: {
        'content-type': 'application/json; charset=utf-8',
        'content-disposition': `attachment; filename="${safeFilename(snapshot.generation_id, 'json')}"`,
        'content-length': String(Buffer.byteLength(serialized)),
        'cache-control': 'no-store',
        'x-content-type-options': 'nosniff',
        'x-ckk-generation': generationHeader,
      },
    });
  }

  const compressed = await gzipAsync(Buffer.from(serialized, 'utf8'));
  return new Response(compressed, {
    headers: {
      'content-type': 'application/gzip',
      'content-disposition': `attachment; filename="${safeFilename(snapshot.generation_id, 'json.gz')}"`,
      'content-length': String(compressed.byteLength),
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      'x-ckk-generation': generationHeader,
    },
  });
}

export async function handleExport(request, overrides = {}) {
  const format = new URL(request?.url || 'http://localhost/.netlify/functions/export-graph')
    .searchParams.get('format') || 'summary';
  if (!SUPPORTED_FORMATS.has(format)) {
    return jsonResponse({
      error: `Unsupported export format: ${format}`,
      supported_formats: [...SUPPORTED_FORMATS],
    }, { status: 400 });
  }

  const databaseUrl = overrides.databaseUrl ?? process.env.DATABASE_URL;
  if (!databaseUrl) return jsonResponse({ error: 'DATABASE_URL missing' }, { status: 503 });
  const connect = overrides.connect ?? neon;
  const readSnapshot = overrides.readSnapshot ?? readLegacySnapshot;
  const now = overrides.now ?? (() => new Date().toISOString());

  try {
    const snapshot = await readSnapshot(connect(databaseUrl));
    return await createExportResponse(request, snapshot, now());
  } catch (error) {
    return jsonResponse({ error: String(error) }, { status: 500 });
  }
}

export default handleExport;
