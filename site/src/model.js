export const GOLDEN = Object.freeze({
  generationId: 'v6-noselfdual-563f50e328c5',
  grammarVersion: 'v6-html-no-asserted-selfdual',
  runId: '34',
  nodes: 276,
  edges: 945,
  legacyConvergences: 196,
  sourceSha256: '8627e79c0b7ef61a2d989290c2250003f837590d37cb2c99fa9c31d008335a90',
});

export const DOMAINS = Object.freeze({
  physics: {
    name: 'PHYSICS', status: 'FOUND_EXACT', executable: true, structures: 276,
    center: [0, 0, 0], color: 0x62d9ff,
    note: 'The sealed Run 34 graph is available as a complete, validated historical presentation snapshot.',
  },
  chemistry: {
    name: 'CHEMISTRY', status: 'FOUND_PARTIAL', executable: false, structures: 0,
    center: [290, 75, -90], color: 0xc17dff,
    note: 'A sealed exclusion/occupancy methodology survives, but no executable seed list, output fixture, or hold-out catalog was recovered.',
    provenance: 'SEALED_EXCLUSION.md', missing: 'EXECUTABLE SEEDS + FROZEN OUTPUT + HOLD-OUTS',
  },
  biology: {
    name: 'BIOLOGY', status: 'FOUND_PARTIAL', executable: false, structures: 0,
    center: [-275, 90, -130], color: 0x65e6ad,
    note: 'A sealed finite-recurrence methodology survives, but no executable biological seed list or frozen result set was recovered.',
    provenance: 'SEALED_ZN.md', missing: 'EXECUTABLE SEEDS + FROZEN OUTPUT + HOLD-OUTS',
  },
  computation: {
    name: 'COMPUTATION', status: 'FOUND_PARTIAL', executable: false, structures: 0,
    center: [60, -205, -210], color: 0xff7caa,
    note: 'A sealed structural-involution methodology survives, but no executable computation fixture was recovered. Self-duality remains not evaluated.',
    provenance: 'SEALED_DUALITY.md', missing: 'EXECUTABLE SEEDS + FROZEN OUTPUT + HOLD-OUTS',
  },
});

export const STATUS_MEANING = Object.freeze({
  KNOWN: 'Matches a structure intentionally present in the historical reference catalog.',
  REDISCOVERED: 'Run 34 records a held-out/catalog match after structural generation.',
  VARIANT: 'A generated structural relative of a catalog entry; it is not an exact match claim.',
  UNMATCHED: 'A valid generated structure with no assigned catalog match in Run 34.',
});

const KIND_MEANING = Object.freeze({
  RECURRENCE: 'A minimal repeated relation used as a structural seed.',
  SYMMETRY: 'A seed carrying a recorded symmetry signature.',
  BOUNDCOND: 'A seed carrying a boundary-condition class.',
  CARRIER: 'A seed carrying an occupancy constraint.',
  CYCLE: 'A generated closed one-dimensional structural class.',
  INTEGER: 'A generated discrete counting class associated with a closed structure.',
  PRODUCT: 'A generated composition whose stored dimension is the product dimension.',
  BUNDLE: 'A generated base/fiber structural class.',
  BOUNDARY: 'A generated boundary structural class.',
  WEIGHT: 'A generated weighted structural class.',
  FILTER: 'A generated filtered structural class.',
});

const CATALOG_FORMULAS = Object.freeze({
  '76': 'eⁱᶲ,  φ ≡ φ + 2π',
  '151': '(1/2π) ∮ dφ = n,  n ∈ ℤ',
  '314': 'C⃗ = (C₁, C₂, C₃)',
  '331': 'C₂ = (1/8π²) ∫ Tr(F ∧ F) ∈ ℤ',
});

export function structuralSignature(node) {
  return [
    node.kind, Number(node.dim), Number(node.recurrence_order ?? 0),
    node.symmetry ?? null, node.sq ?? null, node.anti ?? null,
    Number(node.multiplicity ?? 1), node.boundary_condition ?? null,
    Number(node.dual ?? 0), node.occupancy ?? null,
  ];
}

export function structuralSignatureText(node) {
  const [kind, dim, order, symmetry, sq, anti, mult, bc, dual, occupancy] = structuralSignature(node);
  return `${kind}(dim=${dim}, order=${order}, symmetry=${symmetry ?? '∅'}, square=${sq ?? '∅'}, anti=${anti ?? '∅'}, multiplicity=${mult}, boundary=${bc ?? '∅'}, dual=${dual}, occupancy=${occupancy ?? '∅'})`;
}

export function validateSnapshot(data) {
  const errors = [];
  if (!data || typeof data !== 'object') return { clean: false, errors: ['Snapshot payload is not an object.'] };
  if (data.generation_id !== GOLDEN.generationId) errors.push(`Unexpected generation: ${data.generation_id}`);
  if (data.grammar_version !== GOLDEN.grammarVersion) errors.push(`Unexpected grammar: ${data.grammar_version}`);
  if (String(data.run?.id) !== GOLDEN.runId) errors.push(`Unexpected run: ${data.run?.id}`);
  if (data.nodes?.length !== GOLDEN.nodes) errors.push(`Node count ${data.nodes?.length} != ${GOLDEN.nodes}`);
  if (data.edges?.length !== GOLDEN.edges) errors.push(`Edge count ${data.edges?.length} != ${GOLDEN.edges}`);
  if (data.duality_clusters?.length !== GOLDEN.legacyConvergences) errors.push(`Legacy convergence count ${data.duality_clusters?.length} != ${GOLDEN.legacyConvergences}`);
  if (data.summary?.structures !== data.nodes?.length) errors.push('Summary node count does not match payload.');
  if (data.summary?.relations !== data.edges?.length) errors.push('Summary edge count does not match payload.');
  const ids = new Set();
  for (const node of data.nodes || []) {
    if (ids.has(String(node.id))) errors.push(`Duplicate node ${node.id}`);
    ids.add(String(node.id));
    if (Number(node.dual) === 2) errors.push(`Unverified self-duality state on node ${node.id}`);
  }
  for (const edge of data.edges || []) {
    if (!ids.has(String(edge.source_id)) || !ids.has(String(edge.target_id))) errors.push(`Dangling edge ${edge.id}`);
    if (String(edge.source_id) === String(edge.target_id)) errors.push(`Self-loop ${edge.id}`);
  }
  if (data.run?.validation?.clean !== true || data.validation?.clean !== true) errors.push('Stored snapshot validation is not clean.');
  return { clean: errors.length === 0, errors };
}

export function buildGraphIndex(data) {
  const nodes = new Map(data.nodes.map((node) => [String(node.id), node]));
  const incoming = new Map(data.nodes.map((node) => [String(node.id), []]));
  const outgoing = new Map(data.nodes.map((node) => [String(node.id), []]));
  for (const edge of data.edges) {
    incoming.get(String(edge.target_id))?.push(edge);
    outgoing.get(String(edge.source_id))?.push(edge);
  }
  const legacyClusters = new Map((data.duality_clusters || []).map((cluster) => [String(cluster.target_node_id), cluster]));
  return { nodes, incoming, outgoing, legacyClusters };
}

export function rootClasses(nodeId, index) {
  const roots = new Set();
  const stack = [String(nodeId)];
  const visited = new Set();
  while (stack.length) {
    const current = stack.pop();
    if (visited.has(current)) continue;
    visited.add(current);
    const parents = index.incoming.get(current) || [];
    if (!parents.length) {
      const node = index.nodes.get(current);
      if (!node) continue;
      if (node.kind === 'CARRIER') roots.add(`CARRIER ${Number(node.occupancy) === 1 ? '+1' : '-1'}`);
      else if (node.kind === 'BOUNDCOND') roots.add(`BOUNDCOND ${node.boundary_condition}`);
      else roots.add(node.kind);
    } else {
      parents.forEach((edge) => stack.push(String(edge.source_id)));
    }
  }
  return [...roots].sort();
}

export function truthCounts(nodes) {
  return nodes.reduce((counts, node) => {
    counts[node.verdict] = (counts[node.verdict] || 0) + 1;
    return counts;
  }, {});
}

export function buildCrossDomainBridges(occurrences) {
  const bySignature = new Map();
  for (const occurrence of occurrences) {
    const signature = JSON.stringify(structuralSignature(occurrence.node));
    if (!bySignature.has(signature)) bySignature.set(signature, []);
    bySignature.get(signature).push(occurrence);
  }
  return [...bySignature.entries()].flatMap(([signature, matches]) => {
    const domains = [...new Set(matches.map((match) => match.domain))];
    return domains.length > 1 ? [{ signature: JSON.parse(signature), domains, occurrences: matches, status: 'STRUCTURAL_MATCH' }] : [];
  });
}

export function nodeCardModel(node, index) {
  const incoming = index.incoming.get(String(node.id)) || [];
  const outgoing = index.outgoing.get(String(node.id)) || [];
  const roots = rootClasses(node.id, index);
  const snapshot = node.signature?.snapshot_node || {};
  const isCatalog = node.verdict === 'KNOWN' || node.verdict === 'REDISCOVERED' || node.verdict === 'VARIANT';
  const legacy = index.legacyClusters.get(String(node.id));
  return {
    id: String(node.id),
    name: node.label || `${node.kind} · d${node.dim}`,
    status: node.verdict,
    statusMeaning: STATUS_MEANING[node.verdict] || 'No status definition is available.',
    meaning: KIND_MEANING[node.kind] || 'A generated structural class recorded in the sealed snapshot.',
    structuralFormula: structuralSignatureText(node),
    catalogFormula: CATALOG_FORMULAS[String(node.id)] || null,
    isCatalog,
    incoming,
    outgoing,
    roots,
    rootDiversity: roots.length,
    factor: snapshot.factor ?? '—',
    physicsRealizations: snapshot.phys || [],
    legacyConvergence: Boolean(legacy),
    legacyParentCount: legacy?.parent_count || 0,
    trueConfluence: 'NOT_VERIFIABLE_FROM_SNAPSHOT',
    provenance: incoming.length && incoming.every((edge) => String(edge.operator).startsWith('snapshot_v6:')) ? 'REQUIRES_PROVENANCE' : incoming.length ? 'STORED_OPERATOR_NAMES' : 'SEED',
    raw: node,
  };
}

export const TOUR = Object.freeze([
  { nodeId: '22', title: 'Recurrence', body: 'Begin with a minimal repeated relation. This is an admitted seed, not a physical interpretation.' },
  { nodeId: '76', title: 'Closure', body: 'Run 34 contains a generated CYCLE at structural dimension 1. Its U(1) meaning is catalog annotation.' },
  { nodeId: '151', title: 'Quantization', body: 'A generated INTEGER class is matched to several known closed-phase realizations in the historical catalog.' },
  { nodeId: '257', title: 'Composition', body: 'A structural PRODUCT reaches dimension 2. Dimension here is structural and constrained by MAXDIM.' },
  { nodeId: '314', title: 'Rediscovered beacon', body: 'Run 34 marks this BUNDLE d3 catalog match as REDISCOVERED. The claim belongs to the sealed historical run.' },
  { nodeId: '316', title: 'Open structure', body: 'This high-path PRODUCT d3 has no assigned catalog match. It is interesting as structure, not a discovery claim.' },
  { nodeId: '331', title: 'Higher dimension', body: 'This PRODUCT d4 is a REDISCOVERED catalog match. MAXDIM=4 remains an experiment parameter, not discovered spacetime.' },
]);
