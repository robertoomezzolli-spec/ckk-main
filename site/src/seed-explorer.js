const SUPPORTED_FORMULAS = Object.freeze({
  'e=mc^2': 'probe:einstein:mass-energy',
});

const clean = (value) => String(value ?? '')
  .replace(/²/g, '^2')
  .normalize('NFKC')
  .toLowerCase()
  .replace(/[·×*]/g, '')
  .replace(/²/g, '^2')
  .replace(/\s+/g, '');

export function normalizeSeedExpression(value) {
  const normalized = clean(value);
  return {
    original: String(value ?? '').trim(),
    normalized,
    display: normalized === 'e=mc^2' ? 'E = mc²' : String(value ?? '').trim(),
  };
}

function explicitNodeIds(probe, resolution) {
  const candidates = [
    probe?.attached_node_id,
    typeof probe?.attachment === 'string' ? probe.attachment : null,
    ...(Array.isArray(probe?.attachment) ? probe.attachment : []),
    resolution?.attached_node_id,
    ...(resolution?.anchor_nodes || []),
    ...(resolution?.matched_node_ids || []),
  ];
  return [...new Set(candidates.filter((id) => id !== null && id !== undefined).map(String))];
}

export function resolveSeedExploration(expression, data, index) {
  const parsed = normalizeSeedExpression(expression);
  const expectedProbeId = SUPPORTED_FORMULAS[parsed.normalized] || null;
  const probes = data.external_probes || data.probes || [];
  const probe = probes.find((candidate) => candidate.id === expectedProbeId)
    || probes.find((candidate) => clean(candidate.formula) === parsed.normalized)
    || null;
  const resolution = probe ? (data.probe_resolution?.[probe.id] || data.probe_resolution?.einstein || null) : null;
  const requestedIds = explicitNodeIds(probe, resolution);
  const matchedNodes = requestedIds.map((id) => index.nodes.get(id)).filter(Boolean);
  const matchedIds = new Set(matchedNodes.map((node) => String(node.id)));
  const provenance = (data.edges || []).filter((edge) => matchedIds.has(String(edge.source_id)) || matchedIds.has(String(edge.target_id)));
  const hasExplicitPath = matchedNodes.length > 0;
  return Object.freeze({
    original: parsed.original,
    normalized: parsed.normalized,
    display: parsed.display,
    recognized: Boolean(probe),
    probeId: probe?.id || null,
    verdict: hasExplicitPath ? 'STRUCTURAL_PATH' : 'NO_STRUCTURAL_PATH',
    matchedNodes,
    provenance,
    explanation: hasExplicitPath
      ? 'The selected SEALED generation contains an explicit stored attachment to the listed structures.'
      : probe
        ? 'The formula is stored as an external blind probe, but this SEALED generation contains no explicit structural attachment.'
        : 'The expression has no explicitly supported resolver or attachment in the selected SEALED generation.',
    unsupportedSteps: hasExplicitPath ? [] : ['No generated structure is explicitly attached to this expression.'],
  });
}
