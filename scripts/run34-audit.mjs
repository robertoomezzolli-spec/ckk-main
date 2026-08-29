#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const EXPECTED_RUN34 = Object.freeze({
  generation_id: 'v6-noselfdual-563f50e328c5',
  grammar_version: 'v6-html-no-asserted-selfdual',
  run_id: '34',
  nodes: 276,
  edges: 945,
  confluences: 196,
  verdicts: Object.freeze({ KNOWN: 15, REDISCOVERED: 2, VARIANT: 129, UNMATCHED: 130 }),
  dual_1: 68,
  dual_2: 0,
});

export const RUN34_WAYBACK = Object.freeze({
  created_at_local: '2026-08-27T15:18:31+02:00',
  git: Object.freeze({
    branch: 'backup/pre-run34-audit-20260827-151831',
    tag: 'pre-run34-audit-20260827-151831',
    commit: '7e7b3dbe2b1fc2658403b72f6a754df09813bf70',
    working_tree_stash_commit: 'bd2e5865d2cb41846b7130447890a2720b82cecd',
    preserved_untracked_file: 'agent/graph_export.json',
    preserved_untracked_sha256: '5d3605ff257562fba97c8a697c0784d84b46584fcd9f474e20eabe066bff1106',
  }),
  neon: Object.freeze({
    project_id: 'autumn-bonus-53940783',
    production_branch_id: 'br-wild-hill-awswgush',
    backup_branch_id: 'br-icy-bar-aw2gv084',
    backup_branch_name: 'snapshot-pre-run34-audit-20260827-151831',
    parent_lsn: '0/379BBF8',
    compute_type: 'read_only',
  }),
  production: Object.freeze({
    deployment_id: '6a9035de3b4e5f000812f973',
    deployment_state: 'ready',
    deployment_url: 'https://6a9035de3b4e5f000812f973--ckk-live.netlify.app',
    generation_id: 'v6-noselfdual-563f50e328c5',
    grammar_version: 'v6-html-no-asserted-selfdual',
    run_id: '34',
    node_count: 276,
    edge_count: 945,
    confluence_count: 196,
    git_commit: '7e7b3dbe2b1fc2658403b72f6a754df09813bf70',
  }),
  restore: Object.freeze({
    git_inspection: 'git switch -c restore/pre-run34-audit pre-run34-audit-20260827-151831',
    git_worktree_if_lost: 'git stash apply bd2e5865d2cb41846b7130447890a2720b82cecd',
    neon_command: 'npx neonctl branches restore br-wild-hill-awswgush br-icy-bar-aw2gv084 --project-id autumn-bonus-53940783 --preserve-under-name pre-run34-audit-restore-source',
  }),
});

const ROOT_CLASS_ORDER = Object.freeze([
  'CARRIER +1',
  'CARRIER -1',
  'RECURRENCE',
  'SYMMETRY',
  'BOUNDCOND D',
  'BOUNDCOND N',
]);

const STRUCTURAL_SIGNATURE_FIELDS = Object.freeze([
  'kind',
  'dim',
  'recurrence_order',
  'factor',
  'symmetry',
  'sq',
  'anti',
  'multiplicity',
  'boundary_condition',
  'occupancy',
  'dual',
]);

const DUAL_PARTNER_FIELDS = Object.freeze(
  STRUCTURAL_SIGNATURE_FIELDS.filter((field) => field !== 'dual'),
);

const CHAIN_IDS = Object.freeze(['22', '76', '257', '316', '331']);

function byNumericId(a, b) {
  return Number(a.id) - Number(b.id) || String(a.id).localeCompare(String(b.id));
}

function uniqueSorted(values) {
  return [...new Set(values)].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }));
}

function mapPush(map, key, value) {
  const values = map.get(key) ?? [];
  values.push(value);
  map.set(key, values);
}

function factorOf(node) {
  return node?.signature?.snapshot_node?.factor ?? null;
}

export function compactSignature(node, fields = STRUCTURAL_SIGNATURE_FIELDS) {
  const values = {
    kind: node.kind ?? null,
    dim: node.dim ?? null,
    recurrence_order: node.recurrence_order ?? null,
    factor: factorOf(node),
    symmetry: node.symmetry ?? null,
    sq: node.sq ?? null,
    anti: node.anti ?? null,
    multiplicity: node.multiplicity ?? null,
    boundary_condition: node.boundary_condition ?? null,
    occupancy: node.occupancy ?? null,
    dual: node.dual ?? null,
  };
  return Object.fromEntries(fields.map((field) => [field, values[field]]));
}

function signatureKey(node, fields = STRUCTURAL_SIGNATURE_FIELDS) {
  return JSON.stringify(compactSignature(node, fields));
}

function rootClass(node) {
  if (node.lifecycle !== 'ADMITTED') return null;
  if (node.kind === 'CARRIER' && Number(node.occupancy) === 1) return 'CARRIER +1';
  if (node.kind === 'CARRIER' && Number(node.occupancy) === -1) return 'CARRIER -1';
  if (node.kind === 'RECURRENCE') return 'RECURRENCE';
  if (node.kind === 'SYMMETRY') return 'SYMMETRY';
  if (node.kind === 'BOUNDCOND' && node.boundary_condition === 'D') return 'BOUNDCOND D';
  if (node.kind === 'BOUNDCOND' && node.boundary_condition === 'N') return 'BOUNDCOND N';
  return null;
}

function sortRootClasses(classes) {
  return [...classes].sort((a, b) => ROOT_CLASS_ORDER.indexOf(a) - ROOT_CLASS_ORDER.indexOf(b));
}

function classifyOperator(operator) {
  if (/^op_[a-z0-9_]+$/i.test(operator ?? '')) return 'SEMANTIC_OPERATOR';
  if (/^snapshot_v6:\d+$/.test(operator ?? '')) return 'SNAPSHOT_IDENTIFIER_ONLY';
  return 'NO_USABLE_OPERATOR_PROVENANCE';
}

function provenanceQuality(incomingEdges) {
  if (incomingEdges.length === 0) return 'NO_INCOMING_EDGE';
  const classes = new Set(incomingEdges.map((edge) => classifyOperator(edge.operator)));
  if (classes.size === 1) return [...classes][0];
  return 'MIXED_PROVENANCE';
}

function normalizedStructuralValue(value) {
  return value === null || value === undefined ? '∅' : String(value);
}

export function semanticRiskForParents(parents, rootDiversity) {
  const kinds = new Set(parents.map((node) => normalizedStructuralValue(node.kind)));
  const dimensions = new Set(parents.map((node) => normalizedStructuralValue(node.dim)));
  const boundaries = new Set(parents.map((node) => normalizedStructuralValue(node.boundary_condition)));
  const symmetries = new Set(parents.map((node) => normalizedStructuralValue(node.symmetry)));
  const signatures = new Set(parents.map((node) => signatureKey(node)));
  const flags = {
    heterogeneous_parent_kinds: kinds.size >= 2,
    cross_dimension_parents: dimensions.size >= 2,
    cross_boundary_conditions: boundaries.size >= 2,
    cross_symmetry_classes: symmetries.size >= 2,
    broad_root_mix: rootDiversity >= 4,
    very_high_parent_signature_diversity: signatures.size >= 4,
  };
  const active = Object.entries(flags).filter(([, enabled]) => enabled).map(([name]) => name);
  const high =
    (flags.cross_dimension_parents &&
      (flags.heterogeneous_parent_kinds || flags.cross_boundary_conditions || flags.cross_symmetry_classes)) ||
    active.length >= 4;
  const level = high ? 'HIGH' : active.length >= 2 ? 'MEDIUM' : 'LOW';
  return { level, flags, active_flags: active };
}

function candidateClassification(semanticRisk, quality) {
  if (semanticRisk.level !== 'LOW' && quality === 'SNAPSHOT_IDENTIFIER_ONLY') {
    return 'REQUIRES_PROVENANCE';
  }
  return `${semanticRisk.level}_RISK`;
}

function countBy(items, keyFn) {
  const counts = new Map();
  for (const item of items) {
    const key = String(keyFn(item));
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Object.fromEntries([...counts.entries()].sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true })));
}

function percentage(numerator, denominator) {
  return denominator === 0 ? 0 : Number((numerator / denominator).toFixed(6));
}

function csvEscape(value) {
  if (value === null || value === undefined) return '';
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function csv(rows, columns) {
  return [
    columns.join(','),
    ...rows.map((row) => columns.map((column) => csvEscape(row[column])).join(',')),
  ].join('\n') + '\n';
}

function fullStoredNode(node) {
  return structuredClone(node);
}

function classifySelfDualityAssertion(node) {
  return node.selfdual === true ||
    node.self_dual === true ||
    node.signature?.selfdual === true ||
    node.signature?.self_dual === true ||
    node.signature?.snapshot_node?.selfdual === true ||
    Number(node.dual) >= 2;
}

function graphIndex(snapshot) {
  const nodesById = new Map();
  const duplicateNodeIds = [];
  for (const node of snapshot.nodes) {
    const id = String(node.id);
    if (nodesById.has(id)) duplicateNodeIds.push(id);
    else nodesById.set(id, node);
  }
  const incoming = new Map();
  const outgoing = new Map();
  for (const edge of snapshot.edges) {
    mapPush(incoming, String(edge.target_id), edge);
    mapPush(outgoing, String(edge.source_id), edge);
  }
  return { nodesById, duplicateNodeIds, incoming, outgoing };
}

function rootsForNode(nodeId, index, cache) {
  if (cache.has(nodeId)) return cache.get(nodeId);
  const roots = new Set();
  const visited = new Set();
  const stack = [nodeId];
  while (stack.length > 0) {
    const currentId = stack.pop();
    if (visited.has(currentId)) continue;
    visited.add(currentId);
    const current = index.nodesById.get(currentId);
    if (!current) continue;
    const classification = rootClass(current);
    if (classification) roots.add(classification);
    for (const edge of index.incoming.get(currentId) ?? []) stack.push(String(edge.source_id));
  }
  const result = sortRootClasses(roots);
  cache.set(nodeId, result);
  return result;
}

function detailedNodeRef(node, auditById) {
  const audit = auditById.get(String(node.id));
  return {
    id: String(node.id),
    signature: compactSignature(node),
    depth: node.depth,
    verdict: node.verdict,
    lifecycle: node.lifecycle,
    paths: node.paths,
    indegree: audit.indegree,
    outdegree: audit.outdegree,
    root_classes: audit.root_classes,
    root_diversity: audit.root_diversity,
  };
}

function edgeWithEndpoints(edge, nodesById) {
  return {
    ...edge,
    source_signature: nodesById.has(String(edge.source_id))
      ? compactSignature(nodesById.get(String(edge.source_id)))
      : null,
    target_signature: nodesById.has(String(edge.target_id))
      ? compactSignature(nodesById.get(String(edge.target_id)))
      : null,
    provenance_class: classifyOperator(edge.operator),
  };
}

function adjacentLevel(startIds, direction, index, auditById) {
  const edgeMap = direction === 'parents' ? index.incoming : index.outgoing;
  const endpoint = direction === 'parents' ? 'source_id' : 'target_id';
  const edges = startIds.flatMap((id) => edgeMap.get(String(id)) ?? []);
  const nodeIds = uniqueSorted(edges.map((edge) => String(edge[endpoint])));
  return {
    nodes: nodeIds.map((id) => detailedNodeRef(index.nodesById.get(id), auditById)),
    edges: edges.map((edge) => edgeWithEndpoints(edge, index.nodesById)),
  };
}

function rankCandidates(a, b) {
  const rank = { REQUIRES_PROVENANCE: 3, HIGH_RISK: 2, MEDIUM_RISK: 1, LOW_RISK: 0 };
  return (rank[b.classification] - rank[a.classification]) ||
    (b.root_diversity - a.root_diversity) ||
    (b.parent_signature_diversity - a.parent_signature_diversity) ||
    (b.unique_parents - a.unique_parents) ||
    (b.paths - a.paths) ||
    byNumericId(a, b);
}

function buildHardIntegrity(snapshot, index) {
  const nodeIds = new Set(snapshot.nodes.map((node) => String(node.id)));
  const dangling = snapshot.edges.filter(
    (edge) => !nodeIds.has(String(edge.source_id)) || !nodeIds.has(String(edge.target_id)),
  );
  const selfLoops = snapshot.edges.filter((edge) => String(edge.source_id) === String(edge.target_id));
  const confluenceIds = snapshot.nodes
    .filter((node) => (index.incoming.get(String(node.id)) ?? []).length >= 2)
    .map((node) => String(node.id));
  const verdicts = countBy(snapshot.nodes, (node) => node.verdict);
  const duals = countBy(snapshot.nodes, (node) => node.dual);
  const assertions = snapshot.nodes.filter(classifySelfDualityAssertion).map((node) => String(node.id));
  const measured = {
    nodes: snapshot.nodes.length,
    edges: snapshot.edges.length,
    confluences_by_indegree_gte_2: confluenceIds.length,
    confluence_node_ids: confluenceIds,
    verdicts,
    dangling_edges: dangling.length,
    dangling_edge_ids: dangling.map((edge) => String(edge.id)),
    self_loops: selfLoops.length,
    self_loop_edge_ids: selfLoops.map((edge) => String(edge.id)),
    duplicate_node_ids: index.duplicateNodeIds.length,
    duplicate_node_id_values: uniqueSorted(index.duplicateNodeIds),
    dual_counts: duals,
    unverified_selfduality_claims: assertions.length,
    unverified_selfduality_node_ids: assertions,
  };
  const checks = {
    generation_id: snapshot.generation_id === EXPECTED_RUN34.generation_id,
    grammar_version: (snapshot.grammar_version ?? snapshot.run?.grammar_version) === EXPECTED_RUN34.grammar_version,
    run_id: String(snapshot.run?.id) === EXPECTED_RUN34.run_id,
    nodes: measured.nodes === EXPECTED_RUN34.nodes,
    edges: measured.edges === EXPECTED_RUN34.edges,
    confluences: measured.confluences_by_indegree_gte_2 === EXPECTED_RUN34.confluences,
    known: Number(verdicts.KNOWN ?? 0) === EXPECTED_RUN34.verdicts.KNOWN,
    rediscovered: Number(verdicts.REDISCOVERED ?? 0) === EXPECTED_RUN34.verdicts.REDISCOVERED,
    variant: Number(verdicts.VARIANT ?? 0) === EXPECTED_RUN34.verdicts.VARIANT,
    unmatched: Number(verdicts.UNMATCHED ?? 0) === EXPECTED_RUN34.verdicts.UNMATCHED,
    dangling_edges: measured.dangling_edges === 0,
    self_loops: measured.self_loops === 0,
    duplicate_node_ids: measured.duplicate_node_ids === 0,
    dual_2: Number(duals['2'] ?? 0) === EXPECTED_RUN34.dual_2,
    unverified_selfduality_claims: measured.unverified_selfduality_claims === 0,
    methodology_selfduality_not_evaluated:
      snapshot.methodology?.self_duality?.assessment === 'NOT_EVALUATED',
    conservative_projection_disclosed:
      snapshot.run?.note?.includes('Conservative projection of sealed run 33') === true,
  };
  return { status: Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL', checks, measured };
}

function buildNodeAudits(snapshot, index) {
  const rootsCache = new Map();
  return snapshot.nodes.map((node) => {
    const id = String(node.id);
    const incomingEdges = index.incoming.get(id) ?? [];
    const outgoingEdges = index.outgoing.get(id) ?? [];
    const uniqueParentIds = uniqueSorted(incomingEdges.map((edge) => String(edge.source_id)));
    const uniqueChildIds = uniqueSorted(outgoingEdges.map((edge) => String(edge.target_id)));
    const parents = uniqueParentIds.map((parentId) => index.nodesById.get(parentId)).filter(Boolean);
    const roots = rootsForNode(id, index, rootsCache);
    const quality = provenanceQuality(incomingEdges);
    const risk = semanticRiskForParents(parents, roots.length);
    return {
      id,
      kind: node.kind ?? null,
      dim: node.dim ?? null,
      depth: node.depth ?? null,
      verdict: node.verdict ?? null,
      lifecycle: node.lifecycle ?? null,
      factor: factorOf(node),
      symmetry: node.symmetry ?? null,
      multiplicity: node.multiplicity ?? null,
      boundary_condition: node.boundary_condition ?? null,
      occupancy: node.occupancy ?? null,
      dual: node.dual ?? null,
      paths: node.paths ?? null,
      indegree: incomingEdges.length,
      outdegree: outgoingEdges.length,
      unique_parents: uniqueParentIds.length,
      unique_children: uniqueChildIds.length,
      root_classes: roots,
      root_diversity: roots.length,
      catalog_match: node.catalog_match ?? null,
      confluence: incomingEdges.length >= 2,
      provenance_quality: quality,
      semantic_risk: risk.level,
      semantic_risk_flags: risk.active_flags,
      parent_signature_diversity: new Set(parents.map((parent) => signatureKey(parent))).size,
    };
  });
}

function buildRootDiversity(nodeAudits) {
  return {
    root_class_definitions: Object.fromEntries(ROOT_CLASS_ORDER.map((rootClass) => [
      rootClass,
      nodeAudits.filter((node) => node.lifecycle === 'ADMITTED' && node.root_classes.includes(rootClass)).map((node) => node.id),
    ])),
    by_diversity: countBy(nodeAudits, (node) => node.root_diversity),
    by_root_combination: countBy(nodeAudits, (node) => node.root_classes.length ? node.root_classes.join(' + ') : 'NO_REACHABLE_STORED_ROOT'),
  };
}

function buildConfluenceAudits(snapshot, index, nodeAudits) {
  const auditById = new Map(nodeAudits.map((node) => [node.id, node]));
  const confluences = nodeAudits.filter((node) => node.confluence).map((nodeAudit) => {
    const node = index.nodesById.get(nodeAudit.id);
    const incomingEdges = index.incoming.get(nodeAudit.id) ?? [];
    const parentIds = uniqueSorted(incomingEdges.map((edge) => String(edge.source_id)));
    const parents = parentIds.map((id) => index.nodesById.get(id)).filter(Boolean);
    const risk = semanticRiskForParents(parents, nodeAudit.root_diversity);
    const classification = candidateClassification(risk, nodeAudit.provenance_quality);
    return {
      id: nodeAudit.id,
      kind: node.kind,
      dim: node.dim,
      verdict: node.verdict,
      paths: Number(node.paths ?? 0),
      root_classes: nodeAudit.root_classes,
      root_diversity: nodeAudit.root_diversity,
      unique_parents: parentIds.length,
      parent_ids: parentIds,
      parent_kinds: uniqueSorted(parents.map((parent) => normalizedStructuralValue(parent.kind))),
      parent_dimensions: uniqueSorted(parents.map((parent) => normalizedStructuralValue(parent.dim))),
      parent_boundary_conditions: uniqueSorted(parents.map((parent) => normalizedStructuralValue(parent.boundary_condition))),
      parent_symmetry_classes: uniqueSorted(parents.map((parent) => normalizedStructuralValue(parent.symmetry))),
      parent_signature_diversity: new Set(parents.map((parent) => signatureKey(parent))).size,
      provenance_quality: nodeAudit.provenance_quality,
      semantic_risk: risk.level,
      semantic_risk_flags: risk.active_flags,
      classification,
      audit_vector: {
        root_diversity: nodeAudit.root_diversity,
        unique_parents: parentIds.length,
        paths: Number(node.paths ?? 0),
        parent_signature_diversity: new Set(parents.map((parent) => signatureKey(parent))).size,
        provenance_quality: nodeAudit.provenance_quality,
        semantic_risk: risk.level,
      },
      incoming_edges: incomingEdges.map((edge) => edgeWithEndpoints(edge, index.nodesById)),
      parent_records: parents.map((parent) => detailedNodeRef(parent, auditById)),
    };
  });
  const sorted = confluences.sort(rankCandidates);
  return {
    count: sorted.length,
    classification_distribution: countBy(sorted, (entry) => entry.classification),
    semantic_risk_distribution: countBy(sorted, (entry) => entry.semantic_risk),
    ranking_method:
      'Lexicographic: classification(REQUIRES_PROVENANCE > HIGH > MEDIUM > LOW), root_diversity, parent_signature_diversity, unique_parents, paths, numeric node id.',
    all: sorted,
    top_25: sorted.slice(0, 25),
  };
}

function buildNode316(index, nodeAudits) {
  const auditById = new Map(nodeAudits.map((node) => [node.id, node]));
  const node = index.nodesById.get('316');
  const parentLevel1 = adjacentLevel(['316'], 'parents', index, auditById);
  const parentLevel2 = adjacentLevel(parentLevel1.nodes.map((item) => item.id), 'parents', index, auditById);
  const childLevel1 = adjacentLevel(['316'], 'children', index, auditById);
  const childLevel2 = adjacentLevel(childLevel1.nodes.map((item) => item.id), 'children', index, auditById);
  const incoming = index.incoming.get('316') ?? [];
  const outgoing = index.outgoing.get('316') ?? [];
  const nodeAudit = auditById.get('316');
  const directParents = parentLevel1.nodes.map((item) => index.nodesById.get(item.id));
  return {
    stored_node: fullStoredNode(node),
    audit_record: nodeAudit,
    parent_signature_diversity: new Set(directParents.map((parent) => signatureKey(parent))).size,
    incoming_path_weight_sum: incoming.reduce((sum, edge) => sum + Number(edge.paths ?? 0), 0),
    outgoing_path_weight_sum: outgoing.reduce((sum, edge) => sum + Number(edge.paths ?? 0), 0),
    parents: { level_1: parentLevel1, level_2: parentLevel2 },
    children: { level_1: childLevel1, level_2: childLevel2 },
    relation_to_257: {
      direct_edges: incoming.filter((edge) => String(edge.source_id) === '257').map((edge) => edgeWithEndpoints(edge, index.nodesById)),
      interpretation: 'STORED_DIRECT_PARENT_RELATION_ONLY',
    },
    relation_to_331: {
      direct_edges: outgoing.filter((edge) => String(edge.target_id) === '331').map((edge) => edgeWithEndpoints(edge, index.nodesById)),
      interpretation: 'STORED_DIRECT_CHILD_RELATION_ONLY',
    },
    caveat: 'All edge operators are reported exactly as stored. No missing operator semantics are reconstructed.',
  };
}

function buildDimensionChain(index) {
  const nodes = CHAIN_IDS.map((id) => ({ id, stored_signature: fullStoredNode(index.nodesById.get(id)) }));
  const edges = [];
  for (let position = 0; position < CHAIN_IDS.length - 1; position += 1) {
    const source = CHAIN_IDS[position];
    const target = CHAIN_IDS[position + 1];
    const matches = (index.outgoing.get(source) ?? []).filter((edge) => String(edge.target_id) === target);
    edges.push({
      source,
      target,
      exists: matches.length > 0,
      stored_edges: matches.map((edge) => edgeWithEndpoints(edge, index.nodesById)),
      operator_semantics: matches.every((edge) => classifyOperator(edge.operator) === 'SNAPSHOT_IDENTIFIER_ONLY')
        ? 'NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER'
        : 'SEE_STORED_EDGE_PROVENANCE',
    });
  }
  return { node_ids: CHAIN_IDS, nodes, edges };
}

function buildDimensionTransitions(snapshot, index) {
  const dimensions = uniqueSorted(snapshot.nodes.map((node) => Number(node.dim)));
  const nodesPerDimension = new Map(dimensions.map((dim) => [String(dim), snapshot.nodes.filter((node) => Number(node.dim) === Number(dim)).length]));
  const rows = [];
  for (const sourceDim of dimensions) {
    for (const targetDim of dimensions) {
      const edges = snapshot.edges.filter((edge) => {
        const source = index.nodesById.get(String(edge.source_id));
        const target = index.nodesById.get(String(edge.target_id));
        return Number(source?.dim) === Number(sourceDim) && Number(target?.dim) === Number(targetDim);
      });
      const sourceIds = uniqueSorted(edges.map((edge) => String(edge.source_id)));
      const targetIds = uniqueSorted(edges.map((edge) => String(edge.target_id)));
      rows.push({
        transition: `d${sourceDim}->d${targetDim}`,
        source_dim: Number(sourceDim),
        target_dim: Number(targetDim),
        edge_count: edges.length,
        unique_sources: sourceIds.length,
        unique_targets: targetIds.length,
        total_source_nodes: nodesPerDimension.get(String(sourceDim)),
        total_target_nodes: nodesPerDimension.get(String(targetDim)),
        source_coverage: percentage(sourceIds.length, nodesPerDimension.get(String(sourceDim))),
        target_coverage: percentage(targetIds.length, nodesPerDimension.get(String(targetDim))),
        average_fan_out: percentage(edges.length, sourceIds.length),
        average_fan_in: percentage(edges.length, targetIds.length),
        source_target_ratio: percentage(sourceIds.length, targetIds.length),
      });
    }
  }
  return { dimensions, nodes_per_dimension: Object.fromEntries(nodesPerDimension), rows };
}

function buildDuality(snapshot, index) {
  const byNeutralSignature = new Map();
  for (const node of snapshot.nodes.filter((node) => Number(node.dual) === 0)) {
    mapPush(byNeutralSignature, signatureKey(node, DUAL_PARTNER_FIELDS), node);
  }
  const rows = snapshot.nodes.filter((node) => Number(node.dual) === 1).sort(byNumericId).map((node) => {
    const candidates = byNeutralSignature.get(signatureKey(node, DUAL_PARTNER_FIELDS)) ?? [];
    const uniquePartner = candidates.length === 1 ? candidates[0] : null;
    const between = uniquePartner
      ? snapshot.edges.filter((edge) =>
        (String(edge.source_id) === String(uniquePartner.id) && String(edge.target_id) === String(node.id)) ||
        (String(edge.source_id) === String(node.id) && String(edge.target_id) === String(uniquePartner.id)))
      : [];
    const semanticDualEdges = between.filter((edge) => edge.operator === 'op_dual');
    return {
      node_id: String(node.id),
      partner_status: candidates.length === 1 ? 'UNIQUE_SIGNATURE_PARTNER' : candidates.length === 0 ? 'NO_SIGNATURE_PARTNER' : 'AMBIGUOUS_SIGNATURE_PARTNER',
      partner_id: uniquePartner ? String(uniquePartner.id) : null,
      partner_candidate_ids: candidates.map((candidate) => String(candidate.id)),
      signature_without_dual_equal: uniquePartner ? signatureKey(node, DUAL_PARTNER_FIELDS) === signatureKey(uniquePartner, DUAL_PARTNER_FIELDS) : null,
      stored_edges_between_pair: between.map((edge) => edgeWithEndpoints(edge, index.nodesById)),
      semantic_op_dual_edges: semanticDualEdges.map((edge) => String(edge.id)),
      involution_test: 'NOT_VERIFIABLE_FROM_SNAPSHOT',
      self_duality: 'NOT_EVALUATED',
    };
  });
  return {
    counts: countBy(snapshot.nodes, (node) => node.dual),
    partner_method: `Unique equality on stored fields excluding dual: ${DUAL_PARTNER_FIELDS.join(', ')}. This is candidate pairing, not operator proof.`,
    involution_assessment: 'NOT_VERIFIABLE_FROM_SNAPSHOT',
    self_duality_assessment: 'NOT_EVALUATED',
    rows,
  };
}

function buildControlAudit(snapshot, nodeAudits) {
  const auditById = new Map(nodeAudits.map((node) => [node.id, node]));
  const controls = snapshot.nodes.filter((node) => node.verdict === 'KNOWN' || node.verdict === 'REDISCOVERED').sort(byNumericId).map((node) => {
    const audit = auditById.get(String(node.id));
    return {
      node_id: String(node.id),
      verdict: node.verdict,
      label: node.label ?? null,
      signature: compactSignature(node),
      paths: node.paths,
      indegree: audit.indegree,
      root_diversity: audit.root_diversity,
      root_classes: audit.root_classes,
      confluence: audit.confluence,
      catalog_match: node.catalog_match ?? null,
    };
  });
  return {
    known_count: controls.filter((node) => node.verdict === 'KNOWN').length,
    rediscovered_count: controls.filter((node) => node.verdict === 'REDISCOVERED').length,
    nodes: controls,
    highlighted_stored_claims: {
      node_314: controls.find((node) => node.node_id === '314') ?? null,
      node_331: controls.find((node) => node.node_id === '331') ?? null,
    },
    caveat: 'This section reports only labels and catalog-match flags stored in Run 34; it performs no external physics validation.',
  };
}

function buildUnmatchedAudit(snapshot, nodeAudits, confluenceAudits) {
  const unmatched = nodeAudits.filter((node) => node.verdict === 'UNMATCHED');
  const confluenceById = new Map(confluenceAudits.all.map((entry) => [entry.id, entry]));
  const candidateConfluences = unmatched.map((node) => confluenceById.get(node.id)).filter(Boolean).sort(rankCandidates);
  return {
    count: unmatched.length,
    by_dimension: countBy(unmatched, (node) => node.dim),
    by_kind: countBy(unmatched, (node) => node.kind),
    by_paths: countBy(unmatched, (node) => node.paths),
    by_root_diversity: countBy(unmatched, (node) => node.root_diversity),
    by_confluence: countBy(unmatched, (node) => node.confluence ? 'YES' : 'NO'),
    ranking_method: confluenceAudits.ranking_method,
    top_candidates: candidateConfluences.slice(0, 25),
    all_unmatched_confluences: candidateConfluences,
    node_316_rank: candidateConfluences.findIndex((entry) => entry.id === '316') + 1 || null,
  };
}

function buildProvenance(snapshot) {
  const classes = snapshot.edges.map((edge) => classifyOperator(edge.operator));
  return {
    semantic_operator_names: classes.filter((value) => value === 'SEMANTIC_OPERATOR').length,
    snapshot_v6_identifiers: classes.filter((value) => value === 'SNAPSHOT_IDENTIFIER_ONLY').length,
    no_usable_operator_provenance: classes.filter((value) => value === 'NO_USABLE_OPERATOR_PROVENANCE').length,
    operator_value_distribution: countBy(snapshot.edges, (edge) => edge.operator),
    methodological_limit:
      'The conservative Run-34 projection stores synthetic snapshot_v6:* edge identifiers. Historical operator semantics cannot be reconstructed from this snapshot and are never inferred by this audit.',
  };
}

export function auditSnapshot(snapshot, source = {}) {
  const index = graphIndex(snapshot);
  const hardIntegrity = buildHardIntegrity(snapshot, index);
  if (hardIntegrity.status !== 'PASS') {
    const failed = Object.entries(hardIntegrity.checks).filter(([, passed]) => !passed).map(([name]) => name);
    throw new Error(`Run 34 hard-integrity gate failed: ${failed.join(', ')}`);
  }
  const nodeAudits = buildNodeAudits(snapshot, index);
  const confluenceAudits = buildConfluenceAudits(snapshot, index, nodeAudits);
  const report = {
    schema: 'ckk.run34-audit.v1',
    audit_mode: 'READ_ONLY_SNAPSHOT_MEASUREMENT',
    generated_at: new Date().toISOString(),
    wayback: RUN34_WAYBACK,
    source: {
      ...source,
      generation_id: snapshot.generation_id,
      grammar_version: snapshot.grammar_version ?? snapshot.run?.grammar_version,
      run_id: String(snapshot.run?.id),
      run_note: snapshot.run?.note ?? null,
      projection_constraint: 'Conservative projection of historical Run 33; excluded asserted dual=2 nodes and incident edges are not reconstructed.',
      self_duality: 'NOT_EVALUATED',
    },
    methodology: {
      confluence_definition: 'Stored edge indegree(node) >= 2; export summary and exported clusters are not used for classification.',
      root_reconstruction: 'Reverse reachability over stored edges to the six ADMITTED root classes only.',
      parent_signature_fields: STRUCTURAL_SIGNATURE_FIELDS,
      confluence_audit_vector: ['root_diversity', 'unique_parents', 'paths', 'parent_signature_diversity', 'provenance_quality', 'semantic_risk'],
      semantic_risk_rules: {
        flags: {
          heterogeneous_parent_kinds: 'at least 2 distinct stored parent kinds',
          cross_dimension_parents: 'at least 2 distinct stored parent dimensions',
          cross_boundary_conditions: 'at least 2 distinct stored parent boundary conditions, including null as an explicit absence',
          cross_symmetry_classes: 'at least 2 distinct stored parent symmetry values, including null as an explicit absence',
          broad_root_mix: 'root_diversity >= 4',
          very_high_parent_signature_diversity: 'at least 4 distinct stored parent signatures',
        },
        high: 'cross_dimension_parents AND any of heterogeneous_parent_kinds/cross_boundary_conditions/cross_symmetry_classes, OR at least 4 active flags',
        medium: 'not HIGH and at least 2 active flags',
        low: 'fewer than 2 active flags',
        requires_provenance: 'semantic risk is not LOW and all incoming operators are snapshot identifiers',
        non_claim: 'semantic_risk prioritizes possible signature collisions; it is not a physical judgment or proof of error.',
      },
      labels_used_in_risk_or_ranking: false,
      physics_catalog_used_in_risk_or_ranking: false,
    },
    hard_integrity: hardIntegrity,
    root_diversity: buildRootDiversity(nodeAudits),
    nodes: nodeAudits,
    confluences: confluenceAudits,
    node_316: buildNode316(index, nodeAudits),
    dimension_chain: buildDimensionChain(index),
    dimension_transitions: buildDimensionTransitions(snapshot, index),
    duality: buildDuality(snapshot, index),
    known_rediscovered_controls: buildControlAudit(snapshot, nodeAudits),
    unmatched: buildUnmatchedAudit(snapshot, nodeAudits, confluenceAudits),
    provenance: buildProvenance(snapshot),
    change_safety: {
      source_only: true,
      before: { nodes: snapshot.nodes.length, edges: snapshot.edges.length, run_id: String(snapshot.run?.id), generation_id: snapshot.generation_id },
      after: { nodes: snapshot.nodes.length, edges: snapshot.edges.length, run_id: String(snapshot.run?.id), generation_id: snapshot.generation_id },
      graph_changed: false,
    },
  };
  return report;
}

function confluenceCsvRows(confluences) {
  return confluences.map((entry, index) => ({
    rank: index + 1,
    id: entry.id,
    kind: entry.kind,
    dim: entry.dim,
    verdict: entry.verdict,
    classification: entry.classification,
    semantic_risk: entry.semantic_risk,
    semantic_risk_flags: entry.semantic_risk_flags,
    root_classes: entry.root_classes,
    root_diversity: entry.root_diversity,
    unique_parents: entry.unique_parents,
    parent_signature_diversity: entry.parent_signature_diversity,
    paths: entry.paths,
    provenance_quality: entry.provenance_quality,
    parent_ids: entry.parent_ids,
    parent_kinds: entry.parent_kinds,
    parent_dimensions: entry.parent_dimensions,
    parent_boundary_conditions: entry.parent_boundary_conditions,
    parent_symmetry_classes: entry.parent_symmetry_classes,
  }));
}

function markdownSignature(signature) {
  return Object.entries(signature).map(([key, value]) => `${key}=${value ?? 'null'}`).join(', ');
}

function buildNode316Markdown(report) {
  const section = report.node_316;
  const node = section.stored_node;
  const listNodes = (items) => items.length
    ? items.map((item) => `- ${item.id}: ${markdownSignature(item.signature)}; paths=${item.paths}; roots=[${item.root_classes.join(', ')}]`).join('\n')
    : '- none';
  const listEdges = (items) => items.length
    ? items.map((edge) => `- edge ${edge.id}: ${edge.source_id} -> ${edge.target_id}; operator=${edge.operator}; paths=${edge.paths}`).join('\n')
    : '- none';
  return `# Run 34 — Node 316 deep audit

Source generation: \`${report.source.generation_id}\`  
Run: \`${report.source.run_id}\`  
Projection constraint: ${report.source.projection_constraint}  
Self-duality: **NOT_EVALUATED**

## Stored node

- ID: ${node.id}
- Signature: ${markdownSignature(compactSignature(node))}
- Verdict: ${node.verdict}
- Lifecycle: ${node.lifecycle}
- Paths (stored node field): ${node.paths}
- In-degree / out-degree: ${section.audit_record.indegree} / ${section.audit_record.outdegree}
- Unique parents / children: ${section.audit_record.unique_parents} / ${section.audit_record.unique_children}
- Root classes: ${section.audit_record.root_classes.join(', ') || 'none'}
- Root diversity: ${section.audit_record.root_diversity}
- Parent signature diversity: ${section.parent_signature_diversity}
- Incoming / outgoing stored edge path sums: ${section.incoming_path_weight_sum} / ${section.outgoing_path_weight_sum}

No physical interpretation is added. Edge operators are reproduced exactly as stored.

## Direct parents

${listNodes(section.parents.level_1.nodes)}

### Incoming edges

${listEdges(section.parents.level_1.edges)}

## Parents at distance 2

${listNodes(section.parents.level_2.nodes)}

### Distance-2 edge layer

${listEdges(section.parents.level_2.edges)}

## Direct children

${listNodes(section.children.level_1.nodes)}

### Outgoing edges

${listEdges(section.children.level_1.edges)}

## Children at distance 2

${listNodes(section.children.level_2.nodes)}

### Distance-2 edge layer

${listEdges(section.children.level_2.edges)}

## Stored relation to Node 257

${listEdges(section.relation_to_257.direct_edges)}

Classification: ${section.relation_to_257.interpretation}.

## Stored relation to Node 331

${listEdges(section.relation_to_331.direct_edges)}

Classification: ${section.relation_to_331.interpretation}.

## Provenance limit

${section.caveat}
`;
}

function buildAuditMarkdown(report) {
  const top = report.confluences.top_25;
  const transitions = report.dimension_transitions.rows.filter((row) =>
    ['d0->d1', 'd1->d2', 'd2->d3', 'd3->d4'].includes(row.transition));
  const chainEdges = report.dimension_chain.edges;
  return `# CKK Run 34 confluence audit

## Wayback point

- Git branch: \`${report.wayback.git.branch}\`
- Git tag: \`${report.wayback.git.tag}\`
- Ausgangscommit: \`${report.wayback.git.commit}\`
- Working-tree stash: \`${report.wayback.git.working_tree_stash_commit}\`
- Neon production branch: \`${report.wayback.neon.production_branch_id}\`
- Neon backup branch: \`${report.wayback.neon.backup_branch_id}\` (\`${report.wayback.neon.backup_branch_name}\`)
- Neon parent LSN: \`${report.wayback.neon.parent_lsn}\`
- Production deployment: \`${report.wayback.production.deployment_id}\` (ready)

The Git references are pushed, the pre-existing untracked file was reapplied with an unchanged SHA-256, and the read-only Neon backup independently reproduced Run 34 at 276/945/196 before the audit started.

## Scope

- Mode: **READ-ONLY snapshot measurement**
- Source: \`${report.source.filename}\`
- SHA-256: \`${report.source.sha256}\`
- Generation: \`${report.source.generation_id}\`
- Grammar: \`${report.source.grammar_version}\`
- Run: \`${report.source.run_id}\`
- Constraint: ${report.source.projection_constraint}
- Self-duality \`D(X) ≡ X\`: **NOT_EVALUATED**

## Hard integrity — ${report.hard_integrity.status}

| Measure | Recomputed value |
|---|---:|
| Nodes | ${report.hard_integrity.measured.nodes} |
| Edges | ${report.hard_integrity.measured.edges} |
| Confluences (in-degree >= 2) | ${report.hard_integrity.measured.confluences_by_indegree_gte_2} |
| KNOWN | ${report.hard_integrity.measured.verdicts.KNOWN} |
| REDISCOVERED | ${report.hard_integrity.measured.verdicts.REDISCOVERED} |
| VARIANT | ${report.hard_integrity.measured.verdicts.VARIANT} |
| UNMATCHED | ${report.hard_integrity.measured.verdicts.UNMATCHED} |
| Dangling edges | ${report.hard_integrity.measured.dangling_edges} |
| Self-loops | ${report.hard_integrity.measured.self_loops} |
| Duplicate node IDs | ${report.hard_integrity.measured.duplicate_node_ids} |
| dual=2 | ${report.hard_integrity.measured.dual_counts['2'] ?? 0} |
| Unverified self-duality claims | ${report.hard_integrity.measured.unverified_selfduality_claims} |

The confluence count was computed from stored edge in-degree and not copied from the export summary.

## Root diversity

${Object.entries(report.root_diversity.by_diversity).map(([diversity, count]) => `- diversity ${diversity}: ${count} nodes`).join('\n')}

Root classes are reconstructed by reverse reachability to the six stored ADMITTED roots: CARRIER +1, CARRIER -1, RECURRENCE, SYMMETRY, BOUNDCOND D, BOUNDCOND N.

## Confluence quality

Audit vector: \`C(X)=(root_diversity, unique_parents, paths, parent_signature_diversity, provenance_quality, semantic_risk)\`.

Risk is a transparent collision-prioritization heuristic, not a physical judgment. Labels, physics catalog entries, KNOWN and REDISCOVERED status do not enter risk or ranking. Exact rules are stored in \`run34-audit.json.methodology.semantic_risk_rules\`.

Classification distribution:

${Object.entries(report.confluences.classification_distribution).map(([name, count]) => `- ${name}: ${count}`).join('\n')}

### Top 25 possible false-confluence candidates

| Rank | Node | Kind | d | Verdict | Class | Risk | Roots | Parents | Parent signatures | Paths |
|---:|---:|---|---:|---|---|---|---:|---:|---:|---:|
${top.map((entry, index) => `| ${index + 1} | ${entry.id} | ${entry.kind} | ${entry.dim} | ${entry.verdict} | ${entry.classification} | ${entry.semantic_risk} | ${entry.root_diversity} | ${entry.unique_parents} | ${entry.parent_signature_diversity} | ${entry.paths} |`).join('\n')}

No candidate is declared erroneous. \`REQUIRES_PROVENANCE\` means the stored parent heterogeneity cannot be resolved because incoming edges retain only snapshot identifiers.

## Node 316

- Stored signature: ${markdownSignature(compactSignature(report.node_316.stored_node))}
- Stored paths: ${report.node_316.stored_node.paths}
- In-degree / out-degree: ${report.node_316.audit_record.indegree} / ${report.node_316.audit_record.outdegree}
- Root diversity: ${report.node_316.audit_record.root_diversity}
- Parent signature diversity: ${report.node_316.parent_signature_diversity}
- Relation to 257: ${report.node_316.relation_to_257.direct_edges.length} stored direct edge(s)
- Relation to 331: ${report.node_316.relation_to_331.direct_edges.length} stored direct edge(s)
- UNMATCHED confluence rank: ${report.unmatched.node_316_rank}

See \`run34-node316.md\` for two parent and two child levels with raw stored edges.

## Dimension chain 22 -> 76 -> 257 -> 316 -> 331

${chainEdges.map((item) => `- ${item.source} -> ${item.target}: ${item.exists ? 'stored' : 'missing'}; ${item.stored_edges.map((edge) => `edge ${edge.id}, operator=${edge.operator}, paths=${edge.paths}`).join('; ') || 'no edge'}; semantics=${item.operator_semantics}`).join('\n')}

The audit does not reconstruct \`op_close\`, \`op_product\`, or any other operator from \`snapshot_v6:*\` identifiers.

## Dimension transitions

| Transition | Edges | Sources | Targets | Source coverage | Target coverage | Avg fan-out | Avg fan-in |
|---|---:|---:|---:|---:|---:|---:|---:|
${transitions.map((row) => `| ${row.transition} | ${row.edge_count} | ${row.unique_sources} | ${row.unique_targets} | ${row.source_coverage} | ${row.target_coverage} | ${row.average_fan_out} | ${row.average_fan_in} |`).join('\n')}

All 25 measured d0..d4 transitions are in \`run34-dimension-transitions.csv\`. No dimensional transition is interpreted physically.

## Duality

- dual=0: ${report.duality.counts['0'] ?? 0}
- dual=1: ${report.duality.counts['1'] ?? 0}
- dual=2: ${report.duality.counts['2'] ?? 0}
- \`D(D(X))=X\`: **${report.duality.involution_assessment}**
- \`D(X) ≡ X\`: **${report.duality.self_duality_assessment}**

Stored-signature partners are listed only as candidates. No semantic \`op_dual\` provenance survives in the snapshot, so involution is not claimed.

## KNOWN / REDISCOVERED controls

- KNOWN: ${report.known_rediscovered_controls.known_count}
- REDISCOVERED: ${report.known_rediscovered_controls.rediscovered_count}
- Node 314 stored claim: ${report.known_rediscovered_controls.highlighted_stored_claims.node_314?.label ?? 'not present'}
- Node 331 stored claim: ${report.known_rediscovered_controls.highlighted_stored_claims.node_331?.label ?? 'not present'}

These are stored Run-34 claims only; this audit performs no external-physics validation.

## UNMATCHED

- Count: ${report.unmatched.count}
- Confluences: ${report.unmatched.by_confluence.YES ?? 0}
- Non-confluences: ${report.unmatched.by_confluence.NO ?? 0}
- Node 316 objective structural rank: ${report.unmatched.node_316_rank}

Full groupings and raw candidates are in the JSON and CSV outputs.

## Provenance limitation

- Semantic operator names: ${report.provenance.semantic_operator_names}
- \`snapshot_v6:*\` identifiers: ${report.provenance.snapshot_v6_identifiers}
- No usable operator provenance: ${report.provenance.no_usable_operator_provenance}

${report.provenance.methodological_limit}

## Change safety

- Nodes: ${report.change_safety.before.nodes} -> ${report.change_safety.after.nodes}
- Edges: ${report.change_safety.before.edges} -> ${report.change_safety.after.edges}
- Run: ${report.change_safety.before.run_id} -> ${report.change_safety.after.run_id}
- Generation: ${report.change_safety.before.generation_id} -> ${report.change_safety.after.generation_id}
- Graph changed: ${report.change_safety.graph_changed}
`;
}

export async function writeAuditOutputs(report, outputDirectory) {
  await mkdir(outputDirectory, { recursive: true });
  const confluenceColumns = [
    'rank', 'id', 'kind', 'dim', 'verdict', 'classification', 'semantic_risk', 'semantic_risk_flags',
    'root_classes', 'root_diversity', 'unique_parents', 'parent_signature_diversity', 'paths',
    'provenance_quality', 'parent_ids', 'parent_kinds', 'parent_dimensions',
    'parent_boundary_conditions', 'parent_symmetry_classes',
  ];
  const transitionColumns = [
    'transition', 'source_dim', 'target_dim', 'edge_count', 'unique_sources', 'unique_targets',
    'total_source_nodes', 'total_target_nodes', 'source_coverage', 'target_coverage',
    'average_fan_out', 'average_fan_in', 'source_target_ratio',
  ];
  const dualColumns = [
    'node_id', 'partner_status', 'partner_id', 'partner_candidate_ids',
    'signature_without_dual_equal', 'stored_edges_between_pair', 'semantic_op_dual_edges',
    'involution_test', 'self_duality',
  ];
  await Promise.all([
    writeFile(path.join(outputDirectory, 'run34-audit.json'), `${JSON.stringify(report, null, 2)}\n`),
    writeFile(path.join(outputDirectory, 'run34-audit.md'), buildAuditMarkdown(report)),
    writeFile(path.join(outputDirectory, 'run34-top-confluences.csv'), csv(confluenceCsvRows(report.confluences.top_25), confluenceColumns)),
    writeFile(path.join(outputDirectory, 'run34-unmatched-confluences.csv'), csv(confluenceCsvRows(report.unmatched.all_unmatched_confluences), confluenceColumns)),
    writeFile(path.join(outputDirectory, 'run34-dimension-transitions.csv'), csv(report.dimension_transitions.rows, transitionColumns)),
    writeFile(path.join(outputDirectory, 'run34-duality.csv'), csv(report.duality.rows, dualColumns)),
    writeFile(path.join(outputDirectory, 'run34-node316.md'), buildNode316Markdown(report)),
  ]);
}

async function main() {
  const [inputArg, outputArg = 'audit'] = process.argv.slice(2);
  if (!inputArg) {
    throw new Error('Usage: node scripts/run34-audit.mjs <sealed-export.json> [output-directory]');
  }
  const inputPath = path.resolve(inputArg);
  const raw = await readFile(inputPath);
  const snapshot = JSON.parse(raw.toString('utf8'));
  const report = auditSnapshot(snapshot, {
    filename: path.basename(inputPath),
    sha256: createHash('sha256').update(raw).digest('hex'),
    bytes: raw.byteLength,
  });
  await writeAuditOutputs(report, path.resolve(outputArg));
  process.stdout.write(`${JSON.stringify({
    status: report.hard_integrity.status,
    generation_id: report.source.generation_id,
    run_id: report.source.run_id,
    nodes: report.hard_integrity.measured.nodes,
    edges: report.hard_integrity.measured.edges,
    confluences: report.hard_integrity.measured.confluences_by_indegree_gte_2,
    output_directory: path.resolve(outputArg),
  }, null, 2)}\n`);
}

const invokedAsScript = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedAsScript) {
  main().catch((error) => {
    process.stderr.write(`${error.stack ?? error.message}\n`);
    process.exitCode = 1;
  });
}
