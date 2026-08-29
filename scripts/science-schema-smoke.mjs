import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';

const databaseUrl = process.env.SCIENCE_DATABASE_URL;
if (!databaseUrl) throw new Error('SCIENCE_DATABASE_URL missing; production DATABASE_URL is deliberately ignored');
neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: databaseUrl });
const client = await pool.connect();
const result = {};

async function expectBlocked(name, query, parameters = []) {
  await client.query(`SAVEPOINT ${name}`);
  try {
    await client.query(query, parameters);
    result[name] = { blocked: false };
  } catch (error) {
    result[name] = { blocked: true, code: error.code, message: error.message };
    await client.query(`ROLLBACK TO SAVEPOINT ${name}`);
  }
}

try {
  await client.query('BEGIN');
  const cleanId = 'sci-v1-preflight-clean-b5c48f1603ad8b25';
  await expectBlocked('sealed_generation_immutable', "UPDATE science_generations SET grammar_version='forbidden' WHERE id=$1", [cleanId]);
  await expectBlocked('sealed_structure_immutable', "UPDATE science_structures SET kind='FORBIDDEN' WHERE generation_id=$1", [cleanId]);
  await expectBlocked('public_requires_eligible_seal', 'UPDATE science_public_state SET active_generation_id=$1 WHERE singleton=true', [cleanId]);

  await client.query(`INSERT INTO science_canons(id,domain,version,status,payload_hash,frozen_at)
    VALUES('schema-smoke-canon','PHYSICS',999,'FROZEN','schema-smoke-hash',now())`);
  await expectBlocked('frozen_canon_immutable', "UPDATE science_canons SET payload_hash='forbidden' WHERE id='schema-smoke-canon'");
  await client.query('ROLLBACK');

  const legacy = await client.query(`SELECT
    (SELECT id::text FROM runs ORDER BY id DESC LIMIT 1) run_id,
    (SELECT count(*)::int FROM structures) nodes,
    (SELECT count(*)::int FROM edges) edges`);
  const scientific = await client.query(`SELECT
    (SELECT count(*)::int FROM science_generations) generations,
    (SELECT count(*)::int FROM science_seals) seals,
    (SELECT count(*)::int FROM science_failures) failures,
    (SELECT active_generation_id FROM science_public_state WHERE singleton=true) active_public`);
  console.log(JSON.stringify({ trigger_checks: result, legacy_snapshot: legacy.rows[0], scientific_preview: scientific.rows[0] }, null, 2));
} finally {
  client.release();
  await pool.end();
}

