import { analyzeConfluence } from './_grammar.mjs';

export const PHYSICS_CATALOG = [
  { kind: 'CYCLE', dim: 1, order: 0, verdict: 'KNOWN', label: 'Euclidean time / U(1) phase' },
  { kind: 'BOUNDARY', dim: 1, order: 0, verdict: 'KNOWN', label: 'Horizon as boundary' },
  { kind: 'BUNDLE', dim: 1, order: 0, verdict: 'KNOWN', label: 'Aharonov–Bohm bundle / order-parameter phase' },
  { kind: 'INTEGER', dim: 1, order: 0, verdict: 'KNOWN', label: 'Bohr–Sommerfeld · flux quantization · Josephson · double slit' },
  { kind: 'WEIGHT', dim: 1, order: 0, verdict: 'KNOWN', label: 'Interference intensity / Ramsey fringe' },
  { kind: 'FILTER', dim: 1, order: 0, verdict: 'KNOWN', label: 'Greybody factor / diffraction envelope' },
  { kind: 'PRODUCT', dim: 2, order: 0, verdict: 'KNOWN', label: 'Two-frequency torus / Brillouin zone' },
  { kind: 'BUNDLE', dim: 2, order: 0, verdict: 'KNOWN', label: 'Berry bundle / monopole bundle over S²' },
  { kind: 'INTEGER', dim: 2, order: 0, verdict: 'KNOWN', label: 'Chern number · Dirac monopole · Gauss–Bonnet' },
  { kind: 'BUNDLE', dim: 3, order: 0, verdict: 'REDISCOVERED', label: '3D quantum Hall / Chern vector over T³' },
  { kind: 'INTEGER', dim: 3, order: 0, verdict: 'KNOWN', label: 'Wess–Zumino–Witten level' },
  { kind: 'PRODUCT', dim: 4, order: 0, verdict: 'REDISCOVERED', label: '4D quantum Hall / second Chern number' },
  { kind: 'INTEGER', dim: 4, order: 0, verdict: 'KNOWN', label: 'Instanton number / QCD θ sector' },
];

export const EXTERNAL_PROBES = [{
  id: 'probe:einstein:mass-energy',
  name: 'Einstein · mass–energy equivalence',
  formula: 'E = mc²',
  domain: 'Relativity',
  status: 'PROBE',
  attachment: null,
  attached_node_id: null,
  note: 'External known-physics seed. It is not assigned to a CKK node in advance.',
}];

function catalogMatch(node) {
  if (
    node.symmetry != null
    || node.boundary_condition != null
    || Number(node.dual || 0) !== 0
    || node.occupancy != null
    || Number(node.multiplicity || 1) !== 1
  ) return null;
  return PHYSICS_CATALOG.find((entry) =>
    entry.kind === node.kind
    && entry.dim === Number(node.dim)
    && entry.order === Number(node.recurrence_order || 0)) || null;
}

function annotate(nodes, evidence) {
  const evidenceByNode = new Map();
  for (const item of evidence) {
    if (!evidenceByNode.has(item.structure_id)) evidenceByNode.set(item.structure_id, []);
    evidenceByNode.get(item.structure_id).push(item);
  }
  return nodes.map((node) => {
    const catalog = catalogMatch(node);
    const physics = evidenceByNode.get(node.id) || [];
    return catalog ? {
      ...node,
      source_verdict: node.verdict,
      source_label: node.label,
      verdict: catalog.verdict,
      label: catalog.label,
      physics,
      catalog_match: true,
    } : { ...node, physics };
  });
}

function generationIdFor(run) {
  const source = String(run?.source_commit || '');
  if (/^[a-f0-9]{64}$/i.test(source)) {
    const prefix = run?.grammar_version === 'v6-html-no-asserted-selfdual'
      ? 'v6-noselfdual'
      : 'v6-html';
    return `${prefix}-${source.slice(0, 12).toLowerCase()}`;
  }
  return run?.id == null ? null : `legacy-run-${run.id}`;
}

function buildMethodology(nodes) {
  return {
    self_duality: {
      assessment: 'NOT_EVALUATED',
      equivalence_relation: null,
      asserted_flags_present: nodes.filter((node) => Number(node.dual || 0) === 2).length,
      asserted_flags_are_evidence: false,
      reason: 'D(X) ≡ X requires a separately specified and tested structural equivalence.',
    },
    visualization: {
      vertical_axis: 'operator_depth',
      structural_dimension_field: 'nodes[].dim',
      depth_implies_dimension: false,
    },
  };
}

export async function readLegacySnapshot(sql) {
  const queries = [
    sql`SELECT * FROM runs ORDER BY id DESC LIMIT 1`,
    sql`SELECT
        id,kind,dim,recurrence_order,symmetry,sq,anti,multiplicity,
        boundary_condition,dual,occupancy,lifecycle,verdict,paths,depth,label,
        signature,first_seen,last_seen
      FROM structures
      ORDER BY depth,kind,id`,
    sql`SELECT id,source_id,target_id,operator,paths
      FROM edges
      ORDER BY id`,
    sql`SELECT id,created_at,event_type,summary,payload
      FROM discoveries ORDER BY id DESC`,
    sql`SELECT queue.structure_id,queue.priority,queue.status,
        node.kind,node.dim,node.recurrence_order
      FROM research_queue queue
      JOIN structures node ON node.id=queue.structure_id
      ORDER BY queue.priority DESC,queue.structure_id`,
    sql`SELECT structure_id,status,domain,title,claim,source_url,source_date,
        caveat,confidence,created_at
      FROM evidence
      ORDER BY confidence DESC,created_at DESC`,
  ];
  const [runRows, rawNodes, edges, events, queue, evidence] = await sql.transaction(queries, {
    isolationLevel: 'RepeatableRead',
    readOnly: true,
  });
  const sourceRun = runRows[0] || null;
  const nodes = annotate(rawNodes, evidence);
  const dualityClusters = analyzeConfluence(nodes, edges);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const generationId = generationIdFor(sourceRun);
  const methodology = buildMethodology(nodes);
  const validation = {
    run_nodes_match: sourceRun ? Number(sourceRun.node_count) === nodes.length : false,
    run_edges_match: sourceRun ? Number(sourceRun.edge_count) === edges.length : false,
    dangling_edges: edges.filter((edge) =>
      !nodeIds.has(edge.source_id) || !nodeIds.has(edge.target_id)).length,
    self_loops: edges.filter((edge) => edge.source_id === edge.target_id).length,
    duplicate_node_ids: nodes.length - nodeIds.size,
    unverified_selfduality_claims: methodology.self_duality.asserted_flags_present,
  };
  validation.clean = Object.entries(validation).every(([key, value]) =>
    key.endsWith('_match') ? value === true : value === 0);

  const counts = {
    structures: nodes.length,
    relations: edges.length,
    confluences: dualityClusters.length,
    admitted: nodes.filter((node) => node.lifecycle === 'ADMITTED').length,
    generable: nodes.filter((node) => node.lifecycle === 'GENERABLE').length,
    known: nodes.filter((node) => node.verdict === 'KNOWN').length,
    rediscovered: nodes.filter((node) => node.verdict === 'REDISCOVERED').length,
    variants: nodes.filter((node) => node.verdict === 'VARIANT').length,
    unmatched: nodes.filter((node) => node.verdict === 'UNMATCHED').length,
  };
  const run = sourceRun ? {
    ...sourceRun,
    generation_id: generationId,
    status: validation.clean ? 'SEALED' : 'INVALID',
    validation,
  } : null;

  return {
    run,
    nodes,
    edges,
    duality_clusters: dualityClusters,
    events,
    queue,
    evidence,
    probes: EXTERNAL_PROBES,
    probe_resolution: {},
    physics_catalog: PHYSICS_CATALOG,
    methodology,
    counts,
    validation,
    generation_id: generationId,
    grammar_version: sourceRun?.grammar_version || null,
  };
}
