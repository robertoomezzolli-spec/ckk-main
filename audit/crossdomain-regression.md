# CKK Cross-Domain Regression

Result: **BLOCKED_MISSING_GOLDEN_BASELINE / NO NEW GENERATION**

The current core was measured without catalog-label inference. A true confluence requires at least two distinct derivation events for one `structural_sig`; binary input arity is not counted as confluence.

## Domain results

- Physics: **BLOCKED_MISSING_GOLDEN_BASELINE** (FOUND_EXACT)
- Chemistry: **BLOCKED_PARTIAL_HISTORICAL_ARTIFACT** (FOUND_PARTIAL)
- Biology: **BLOCKED_PARTIAL_HISTORICAL_ARTIFACT** (FOUND_PARTIAL)
- Computation: **BLOCKED_PARTIAL_HISTORICAL_ARTIFACT** (FOUND_PARTIAL)

## Current Physics-seed diagnostic

- structural states: 588
- raw derivation events: 2073
- unique derivation events: 1495
- true derivational confluences: 441
- cross-order fiber events: 0
- mixed-dual product events: 0
- mixed-dual fiber events: 0
- self-transition events: 0

Known/rediscovered/variant/unmatched are not evaluated for this current-core diagnostic because no independent current-core catalog/hold-out baseline is frozen.

## Core gates

- `selfdual_operator_absent`: **PASS**
- `dual_structural_roundtrip`: **PASS**
- `fiber_order_compatibility`: **PASS**
- `product_dual_factor_preservation`: **PASS**
- `fiber_dual_factor_preservation`: **PASS**
- `maxdim_disclosed`: **PASS**

`MAXDIM=4` is recorded only as an experiment parameter. It is not evidence for emergent 4D spacetime. Structural dual roundtrip is tested; self-duality remains `NOT_EVALUATED`.

Run 34 remains an unchanged historical presentation snapshot and was not used to fill missing expected outputs.
