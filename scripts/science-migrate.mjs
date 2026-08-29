import { readFile } from 'node:fs/promises';
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';
import { sha256 } from '../science/core.mjs';

const databaseUrl = process.env.SCIENCE_DATABASE_URL;
if (!databaseUrl) throw new Error('SCIENCE_DATABASE_URL missing; production DATABASE_URL is deliberately ignored');
const migrationUrl = new URL('../schema/002_scientific_v1.sql', import.meta.url);
const migration = await readFile(migrationUrl, 'utf8');
neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: databaseUrl });
const client = await pool.connect();
try {
  await client.query(migration);
  await client.query(`INSERT INTO science_migrations(version,checksum) VALUES('002_scientific_v1',$1)
    ON CONFLICT(version) DO UPDATE SET checksum=EXCLUDED.checksum`, [sha256(migration)]);
  const result = await client.query("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'science_%' ORDER BY table_name");
  console.log(JSON.stringify({ migration: '002_scientific_v1', checksum: sha256(migration), tables: result.rows.map((row) => row.table_name) }, null, 2));
} finally {
  client.release();
  await pool.end();
}
