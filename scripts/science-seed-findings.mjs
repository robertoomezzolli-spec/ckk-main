import { readFile } from 'node:fs/promises';
import { ScienceStore } from '../netlify/functions/_science_store.mjs';

const databaseUrl = process.env.SCIENCE_DATABASE_URL;
if (!databaseUrl) throw new Error('SCIENCE_DATABASE_URL missing; production DATABASE_URL is deliberately ignored');
const store = ScienceStore.connect(databaseUrl);
const regression = JSON.parse(await readFile(new URL('../audit/crossdomain-regression.json', import.meta.url), 'utf8'));
const canonicalReplacementSeed = JSON.parse(await readFile(new URL('../audit/canonical-replacement/seed.v1.json', import.meta.url), 'utf8'));
const metrics = regression.domains.physics.current_core_diagnostic;
const findings = [
  {
    domain: 'PHYSICS', code: 'MISSING_OPERATOR', missing_distinction: 'NATIVE_CANONICAL_REPLACEMENT',
    details: {
      summary: 'Derive an irreversible effective many-to-one record transition from native Faecher primitives or fail closed. Partner blocking is not collapse; Landauer is accounting, not outcome selection.',
      source: 'audit/canonical-replacement/seed.v1.json',
      seed_version: canonicalReplacementSeed.seed_version,
      target: canonicalReplacementSeed.target.name,
      success_criterion: canonicalReplacementSeed.success_criterion,
      forbidden_shortcuts: canonicalReplacementSeed.forbidden_shortcuts,
      kill_criteria: canonicalReplacementSeed.kill_criteria,
    },
  },
  {
    domain: 'PHYSICS', code: 'SIGNATURE_COLLISION', missing_distinction: 'BASE_RECURRENCE_ORDER_PRESERVATION',
    details: { summary: 'Current core admits cross-order fiber events; deeper Scientific generations must fail closed.', observed_events: metrics.cross_order_fiber_events, source: 'audit/crossdomain-regression.json' },
  },
  {
    domain: 'PHYSICS', code: 'SIGNATURE_COLLISION', missing_distinction: 'FACTOR_LEVEL_DUAL_STATE',
    details: { summary: 'Current core promotes mixed-dual products without preserving factor-level state.', observed_events: metrics.mixed_dual_product_events, source: 'audit/crossdomain-regression.json' },
  },
  ...['CHEMISTRY', 'BIOLOGY', 'COMPUTATION'].map((domain) => ({
    domain, code: 'INSUFFICIENT_EVIDENCE', missing_distinction: 'EXECUTABLE_DOMAIN_FIXTURE',
    details: { summary: `${domain} has a partial historical method record but no executable frozen seed/output/hold-out suite.`, source: 'audit/crossdomain-golden-suite.json' },
  })),
];
for (const finding of findings) await store.addFailure(finding);
await store.sql`INSERT INTO science_public_state(singleton,active_generation_id) VALUES(true,NULL) ON CONFLICT(singleton) DO NOTHING`;
console.log(JSON.stringify({ seeded_findings: findings.length, public_generation: null }, null, 2));
