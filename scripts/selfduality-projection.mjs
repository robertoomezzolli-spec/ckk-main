import crypto from 'node:crypto';

export const PROJECTION_METHOD = 'exclude-unverified-dual-2-nodes-and-incident-edges';

export function projectUnverifiedSelfduality(nodes, edges) {
  const removedNodes = nodes.filter((node) => Number(node.dual || 0) === 2);
  const keptNodes = nodes.filter((node) => Number(node.dual || 0) !== 2);
  const keptIds = new Set(keptNodes.map((node) => node.id));
  const keptEdges = edges.filter((edge) =>
    keptIds.has(edge.source_id) && keptIds.has(edge.target_id));
  const removedEdges = edges.filter((edge) =>
    !keptIds.has(edge.source_id) || !keptIds.has(edge.target_id));

  return { keptNodes, keptEdges, removedNodes, removedEdges };
}

export function projectionDigest(sourceCommit, projection) {
  const canonical = {
    source_commit: sourceCommit,
    method: PROJECTION_METHOD,
    node_ids: projection.keptNodes.map((node) => node.id).sort(),
    edges: projection.keptEdges
      .map((edge) => [edge.source_id, edge.target_id, edge.operator, Number(edge.paths || 1)])
      .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
  };
  return crypto.createHash('sha256').update(JSON.stringify(canonical)).digest('hex');
}

export function validateProjection(projection) {
  const ids = new Set(projection.keptNodes.map((node) => node.id));
  return {
    asserted_selfduality_nodes: projection.keptNodes.filter((node) =>
      Number(node.dual || 0) === 2).length,
    dangling_edges: projection.keptEdges.filter((edge) =>
      !ids.has(edge.source_id) || !ids.has(edge.target_id)).length,
    self_loops: projection.keptEdges.filter((edge) =>
      edge.source_id === edge.target_id).length,
    duplicate_node_ids: projection.keptNodes.length - ids.size,
  };
}
