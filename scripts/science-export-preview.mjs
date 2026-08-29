import { writeFile } from 'node:fs/promises';
import { ScienceStore } from '../netlify/functions/_science_store.mjs';

const databaseUrl = process.env.SCIENCE_DATABASE_URL;
if (!databaseUrl) throw new Error('SCIENCE_DATABASE_URL missing; production DATABASE_URL is deliberately ignored');
const store = ScienceStore.connect(databaseUrl);
const generations = await store.listGenerations();
const generationDetails = {};
const structureDetails = {};
for (const generation of generations) {
  const detail = await store.generation(generation.id);
  generationDetails[generation.id] = detail;
  for (const structure of detail.structures) {
    structureDetails[`${generation.id}:${structure.id}`] = await store.structure(structure.id, generation.id);
  }
}
const payload = {
  schema: 'ckk.science-preview-export.v1',
  exported_at: new Date().toISOString(),
  source: { plane: 'ISOLATED_NEON_PREVIEW', branch_id: 'br-weathered-smoke-awvboh0k', production: false },
  overview: await store.overview(),
  queue: { candidates: await store.listCandidates() },
  disputes: { disputes: await store.disputes() },
  failures: { failures: await store.failures() },
  'grammar-pressure': await store.grammarPressure(),
  generations: { generations },
  'cross-domain': { matches: await store.crossDomain() },
  generation_details: generationDetails,
  structure_details: structureDetails,
};
await writeFile(new URL('../site/public/data/science-preview.json', import.meta.url), `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
console.log(JSON.stringify({ output: 'site/public/data/science-preview.json', generations: generations.length, structures: Object.keys(structureDetails).length, candidates: payload.queue.candidates.length }, null, 2));

