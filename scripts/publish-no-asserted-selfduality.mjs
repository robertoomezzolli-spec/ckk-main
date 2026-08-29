import { neon } from '@neondatabase/serverless';

import { analyzeConfluence } from '../netlify/functions/_grammar.mjs';
import {
  PROJECTION_METHOD,
  projectUnverifiedSelfduality,
  projectionDigest,
  validateProjection,
} from './selfduality-projection.mjs';

const apply = process.argv.includes('--apply');
const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) throw new Error('DATABASE_URL missing');
const sql = neon(databaseUrl);

const readQueries = [
  sql`SELECT * FROM runs ORDER BY id DESC LIMIT 1`,
  sql`SELECT
      id,kind,dim,recurrence_order,symmetry,sq,anti,multiplicity,
      boundary_condition,dual,occupancy,lifecycle,verdict,paths,depth,label,signature
    FROM structures ORDER BY id`,
  sql`SELECT source_id,target_id,operator,paths FROM edges ORDER BY id`,
];
const [runRows, nodes, edges] = await sql.transaction(readQueries, {
  isolationLevel: 'RepeatableRead',
  readOnly: true,
});
const sourceRun = runRows[0];
if (!sourceRun) throw new Error('No active legacy run');
if (Number(sourceRun.node_count) !== nodes.length || Number(sourceRun.edge_count) !== edges.length) {
  throw new Error('Active run counts do not match the sealed source snapshot');
}

const projection = projectUnverifiedSelfduality(nodes, edges);
const validation = validateProjection(projection);
if (projection.removedNodes.length === 0) {
  throw new Error('No asserted dual=2 nodes found; refusing to republish');
}
if (Object.values(validation).some((value) => value !== 0)) {
  throw new Error(`Candidate validation failed: ${JSON.stringify(validation)}`);
}
const sourceCommit = projectionDigest(sourceRun.source_commit, projection);
const sourceConfluences = analyzeConfluence(nodes, edges).length;
const confluences = analyzeConfluence(projection.keptNodes, projection.keptEdges).length;
const report = {
  mode: apply ? 'APPLY' : 'DRY_RUN',
  source_run_id: sourceRun.id,
  source_grammar_version: sourceRun.grammar_version,
  source_nodes: nodes.length,
  source_edges: edges.length,
  source_confluences: sourceConfluences,
  removed_asserted_selfduality_nodes: projection.removedNodes.length,
  removed_incident_edges: projection.removedEdges.length,
  candidate_nodes: projection.keptNodes.length,
  candidate_edges: projection.keptEdges.length,
  candidate_confluences: confluences,
  candidate_source_commit: sourceCommit,
  method: PROJECTION_METHOD,
  validation,
  caveat: 'Conservative projection of the sealed source snapshot; self-duality is not evaluated.',
};

if (!apply) {
  console.log(JSON.stringify(report, null, 2));
  process.exit(0);
}

const writes = [
  sql`SELECT pg_advisory_xact_lock(hashtext('ckk:legacy-publication'))`,
  sql`DELETE FROM edges`,
  sql`DELETE FROM structures`,
];
for (const node of projection.keptNodes) {
  writes.push(sql`INSERT INTO structures(
      id,kind,dim,recurrence_order,symmetry,sq,anti,multiplicity,
      boundary_condition,dual,occupancy,lifecycle,verdict,paths,depth,label,signature
    ) VALUES(
      ${node.id},${node.kind},${node.dim},${node.recurrence_order},${node.symmetry},
      ${node.sq},${node.anti},${node.multiplicity},${node.boundary_condition},
      ${node.dual},${node.occupancy},${node.lifecycle},${node.verdict},${node.paths},
      ${node.depth},${node.label},${JSON.stringify({
        ...(node.signature || {}),
        projection: {
          method: PROJECTION_METHOD,
          source_run_id: sourceRun.id,
          source_commit: sourceRun.source_commit,
        },
      })}::jsonb
    )`);
}
for (const edge of projection.keptEdges) {
  writes.push(sql`INSERT INTO edges(source_id,target_id,operator,paths)
    VALUES(${edge.source_id},${edge.target_id},${edge.operator},${edge.paths})`);
}
const admitted = projection.keptNodes.filter((node) => node.lifecycle === 'ADMITTED').length;
const unmatched = projection.keptNodes.filter((node) => node.verdict === 'UNMATCHED').length;
writes.push(sql`INSERT INTO runs(
    grammar_version,source_commit,node_count,edge_count,admitted_count,unmatched_count,note
  ) VALUES(
    'v6-html-no-asserted-selfdual',${sourceCommit},${projection.keptNodes.length},
    ${projection.keptEdges.length},${admitted},${unmatched},
    ${`Conservative projection of sealed run ${sourceRun.id}; ${projection.removedNodes.length} asserted dual=2 nodes and ${projection.removedEdges.length} incident edges excluded; self-duality not evaluated.`}
  )`);
writes.push(sql`SELECT count(*)::int AS node_count FROM structures`);
writes.push(sql`SELECT count(*)::int AS edge_count FROM edges`);
writes.push(sql`SELECT count(*)::int AS asserted_selfduality_nodes FROM structures WHERE dual=2`);
writes.push(sql`SELECT count(*)::int AS dangling_edges FROM edges edge
  LEFT JOIN structures source ON source.id=edge.source_id
  LEFT JOIN structures target ON target.id=edge.target_id
  WHERE source.id IS NULL OR target.id IS NULL`);
writes.push(sql`SELECT count(*)::int AS self_loops FROM edges WHERE source_id=target_id`);
writes.push(sql`SELECT * FROM runs ORDER BY id DESC LIMIT 1`);

const results = await sql.transaction(writes, { isolationLevel: 'Serializable' });
const tail = results.slice(-6);
report.persisted = {
  nodes: tail[0][0].node_count,
  edges: tail[1][0].edge_count,
  asserted_selfduality_nodes: tail[2][0].asserted_selfduality_nodes,
  dangling_edges: tail[3][0].dangling_edges,
  self_loops: tail[4][0].self_loops,
  run_id: tail[5][0].id,
};
if (
  report.persisted.nodes !== report.candidate_nodes
  || report.persisted.edges !== report.candidate_edges
  || report.persisted.asserted_selfduality_nodes !== 0
  || report.persisted.dangling_edges !== 0
  || report.persisted.self_loops !== 0
) throw new Error(`Post-publication validation failed: ${JSON.stringify(report.persisted)}`);

console.log(JSON.stringify(report, null, 2));
