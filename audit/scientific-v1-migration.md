# CKK Scientific v1 · Migration report

## Target

- Neon project: `autumn-bonus-53940783`
- Isolated preview branch: `br-weathered-smoke-awvboh0k`
- Branch name: `scientific-v1-preview-20260827-1905`
- Parent production branch: `br-wild-hill-awswgush`
- Parent LSN: `0/387F3D0`
- Production migrated: **NO**
- Migration: `schema/002_scientific_v1.sql`
- Applied checksum: `8414a1e532bbb41479acbf2bea967c0a9d89ef5996a4f1f57efe00b1d5695dda`

## Added tables

17 additive `science_*` tables were created:

`science_adjudications`, `science_agent_runs`, `science_candidates`, `science_canon_targets`, `science_canons`, `science_derivation_events`, `science_evidence`, `science_failures`, `science_generations`, `science_grammar_proposals`, `science_interpretations`, `science_migrations`, `science_normalizations`, `science_public_state`, `science_seals`, `science_structures`, `science_worker_runs`.

No legacy `runs`, `structures`, `edges`, catalog or Run 34 row was altered by the migration.

## Transaction and trigger verification

The migration ran through one Neon WebSocket/Pool session, preserving its explicit `BEGIN`/`COMMIT` boundary. A subsequent test transaction was completely rolled back and proved:

- sealed generation metadata mutation: `BLOCKED`
- sealed structure mutation: `BLOCKED`
- non-public-eligible generation activation: `BLOCKED`
- frozen canon mutation: `BLOCKED`

After rollback the inherited legacy snapshot remained run `34`, `276` nodes and `945` edges. `science_public_state.active_generation_id` remains `null`.

## Preview data

- Five audit-backed initial failures were imported from the sealed cross-domain reports.
- One additional `VALIDATION_FAILED` record was produced by the intentionally rejected level-2 preflight.
- One level-1 preflight generation is sealed with `public_eligible=false`.
- One level-2 preflight generation is rejected and cannot be sealed.

