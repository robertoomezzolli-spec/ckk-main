import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { promisify } from 'node:util';
import { sha256, trueConfluences } from '../science/core.mjs';
import { ScienceStore } from '../netlify/functions/_science_store.mjs';

const execFileAsync = promisify(execFile);
const databaseUrl = process.env.SCIENCE_DATABASE_URL;
if (!databaseUrl) throw new Error('SCIENCE_DATABASE_URL missing; production DATABASE_URL is deliberately ignored');
const store = ScienceStore.connect(databaseUrl);
const [grammarSource, seedFixture] = await Promise.all([
  readFile(new URL('../ckk_snapshot/ckk/gen/grammar.py', import.meta.url), 'utf8'),
  readFile(new URL('../crossdomain/physics/seed.fixture.json', import.meta.url), 'utf8'),
]);
const grammarHash = sha256(grammarSource);
const seedSetHash = sha256(seedFixture);

async function generate(generationId, levels) {
  const { stdout } = await execFileAsync('python3', [
    new URL('./science-generate.py', import.meta.url).pathname,
    '--generation-id', generationId,
    '--levels', String(levels),
    '--operator-version', `ckk-grammar-${grammarHash.slice(0, 12)}`,
  ]);
  return JSON.parse(stdout);
}

async function publish(levels, role) {
  const generationId = `sci-v1-${role}-${sha256({ grammarHash, seedSetHash, levels }).slice(0, 16)}`;
  const payload = await generate(generationId, levels);
  const confluences = trueConfluences(payload.derivation_events);
  await store.persistGeneration({
    id: generationId,
    grammar_version: 'scientific-v1-current-core', grammar_hash: grammarHash, seed_set_hash: seedSetHash,
    maxdim: payload.experiment.maxdim, expansion_levels: levels, true_confluence_count: confluences.length,
    scope: { role: 'CONTROL_PLANE_PREFLIGHT_NO_INTERPRETATION', full_autonomous_cycle: false, public_eligible: false },
  }, payload);
  const validation = await store.validateGeneration(generationId);
  return { generationId, payload, validation };
}

const clean = await publish(1, 'preflight-clean');
if (!clean.validation.clean) throw new Error('Expected level-1 preflight to validate');
const cleanSeal = await store.sealGeneration(clean.generationId, { publicEligible: false });

const rejected = await publish(2, 'preflight-rejected');
if (rejected.validation.clean) throw new Error('Expected deeper current-core preflight to fail');
let rejectedSealBlocked = false;
try { await store.sealGeneration(rejected.generationId, { publicEligible: false }); }
catch { rejectedSealBlocked = true; }
if (!rejectedSealBlocked) throw new Error('Rejected generation was incorrectly sealable');

console.log(JSON.stringify({
  clean: {
    generation_id: clean.generationId,
    structures: clean.payload.structures.length,
    derivation_events: clean.payload.derivation_events.length,
    validation: clean.validation,
    seal: cleanSeal.seal,
  },
  rejected: {
    generation_id: rejected.generationId,
    structures: rejected.payload.structures.length,
    derivation_events: rejected.payload.derivation_events.length,
    validation: rejected.validation,
    seal_blocked: rejectedSealBlocked,
  },
}, null, 2));

