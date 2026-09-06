# Boundary sprint result

The existing rank-lowering boundary operation is now connected to the factor
representation and the existing boundary-as-fiber-base path. No original kernel
or previous experimental dialect was edited. The rule contract is in
`docs/BOUNDARY_ADAPTER_V1.md`; the result JSON pins its hash and both loaded kernel
sources. No external domain lookup or interpretation entered this experiment.

Reproduce:

```bash
python3 scripts/boundary-expansion.py --leaves 3 --depth 3
python3 -m unittest discover -s test -p 'test_boundary_kernel.py' -v
```

Both arms use four recurrence seeds, at most three atomic factor occurrences in
the entire descriptor, and at most three nested fiber/boundary constructors.
Resource budgets are 5,000 nodes, 50,000 applications, 16 frontier rounds and 30
seconds. Both exhausted their bounded frontier, without exhausting those resource
budgets. No global saturation of the unbounded algebra is claimed.

| Measurement | Legacy-compatible projection control | Heterogeneous extension |
| --- | ---: | ---: |
| Recurrence seeds | 4 | 4 |
| Factor states | 24 | 164 |
| Boundary states | 40 | 796 |
| Fiber states | 32 | 1,152 |
| All states | 100 | 2,116 |
| Unique applications, all replayed | 228 | 12,196 |
| Rank-zero boundary/fiber states | 24 | 864 |
| Distinct available legacy scalar projections | 72 | 72 |

All 100 control states occur in the extension. Both controls use the experimental
relative descriptors; the control is not a rerun of the complete old grammar.
There are 2,016 added descriptors without a compatible legacy scalar projection
under these seeds and bounds. There are no additional projected scalar classes
in this run. Thus the result is increased compositional expressivity, not evidence
that a larger list of known domain objects was recovered.

The previous fiber experiment limited base factors to three and then added a
fiber, allowing four leaves total. This sprint limits all roles together to three
leaves. Its fiber count must not be compared directly to the prior 1,312 count.

## Concrete path

The result includes a complete replayed trace for:

1. Close admitted recurrences of orders 2, 3 and 4.
2. Compose the order-2 and order-3 cycles into a two-factor product.
3. Apply boundary: retain both descriptors, lower rank from 2 to 1.
4. Use that boundary as the base with the order-4 cycle as fiber; rank remains 1.
5. Apply boundary again to the fiber structure; rank becomes 0.

All binary co-inputs have their own admitted ancestry. Factor order and product
parenthesization do not change the target. Selective dual transport can address
an intrinsic factor class through the retained base/carrier roles afterward.

## What was checked

Eight boundary tests pass, including original-kernel projection comparisons,
rank-zero cases, the full path, preservation of normal forms, dual involution,
the boundary/dual commuting square, translation from the prior experimental
dialect, resource termination and rehashed corrupt-payload rejection. Independent
constructor counting checks the small saturated run without calling operators.
Nine factor tests, seven fiber tests and fifteen original-kernel tests also pass:
39 tests in these four targeted suites. This is not the full repository test suite.

Every one of the 12,196 applications in the larger run passed replay and
seed-rooted reachability. Replay uses the same operator implementation; independent
evidence comes from the legacy comparisons, algebraic laws and constructor counts.

## Limits retained explicitly

The boundary is a relative carrier/rank descriptor. It contains no orientation,
selected deleted factor, geometric boundary map or physical formula. This preserves
the old scalar rank rule while making the original carrier available downstream;
it does not establish a unique geometric interpretation.

Nested incidence can grow while rank stays at zero. The report separates this
from dimension growth. The chosen structural equivalence does not automatically
identify different incidence towers. A stronger equivalence would require its own
justification and tests.

The sprint now has one frontier generator for close, composition, fiber, boundary
and dual actions. Winding, weight/filter, exclusion/fill and symmetry actions are
still outside this combined dialect. No native DIRECT/INHERITED status, production
database, scientific API or UI was modified.
