# Scientific v1 · First real autonomous seed run — blocked gate

Date: 2026-08-27 Europe/Berlin

## Wayback

- starting commit: `853afb364c7d496c299c1f6eee61f508ad13cde4`
- backup branch: `backup/pre-autonomous-seed-run-20260827-194558`
- backup tag: `pre-autonomous-seed-run-20260827-194558`
- Scientific preview source branch: `br-weathered-smoke-awvboh0k`
- Neon wayback branch: `br-small-haze-aw8x3luf`
- Neon wayback parent LSN: `0/39E1648`
- source LSN at verification: `0/39E1648`
- production remained Run 34 with 276 structures, 945 edges and 196 historical graph confluences

## Root cause and candidate repair

- `op_fiber` discarded the base recurrence order by emitting `fib.order` without requiring equality.
- `op_product` compressed mixed factor dual states through `max(a.dual,b.dual)`.
- `op_fiber` contained the same mixed-dual compression.
- Canonically idempotent applications were retained as self-transition derivation events.

The candidate repair rejects cross-order fiber composition, rejects mixed-dual product/fiber composition because the current signature has no factor-level dual carrier, preserves the common compatible state, and suppresses canonical self-transitions.

## Candidate-repair verification

- Python tests: 26 PASS
- Node tests: 53 PASS
- build: PASS
- structural states at level 4: 588
- derivation events (raw / unique): 2073 / 1495
- true derivational confluences: 441
- cross-order fiber events: 0
- mixed-dual product events: 0
- mixed-dual fiber events: 0
- self-transition events: 0
- dual roundtrip: PASS
- self-duality: NOT_EVALUATED

## Blocking gate

Physics Golden Regression: `BLOCKED_MISSING_GOLDEN_BASELINE`

The repository and its complete Git history contain neither a frozen expected structural-output fixture nor an independent Physics hold-out fixture for the current structural core. Run 34 is a historical presentation projection and is explicitly not interchangeable with a current-core expected output. Freezing the candidate repair's own output after the change would be a post-hoc golden and would violate the no-fixture-adjustment rule.

## Stop state

- external OpenAI calls: 0
- external Anthropic calls: 0
- discovered candidates: 0
- Scientific candidate/evidence/normalization writes: 0
- new Scientific generation: none
- production mutation: none
- Run 34 mutation: none

Decision: `NO-GO` before autonomous fill, as required by the Physics gate.
