# Adapting the existing fiber operator to factor structures

`op_fiber` already exists in `grammar.py`. This work does not claim it was missing. It adapts its ordered base/fiber roles to the experimental factor representation while leaving `grammar.py`, `expand.py` and factor-v1 unchanged.

## Representation and scope

The new FIBER node has exactly three fields: type, base, fiber. The base is a factor-v1 multiset; the fiber is a singleton factor-v1 multiset. Base/fiber roles are intrinsic and ordered. Factor ordering within the base remains canonical and commutative. No history or external label enters node identity.

This representation records incidence and role-specific scalar properties. It does not supply gluing maps, transition functions or any other additional geometry. Its name alone is not a claim to construct arbitrary mathematical bundles.

The original scalar projection retains base dimension and uses fiber occupancy, matching `op_fiber`. It is defined only when both scalar projections exist and order, symmetry, boundary condition and dual agree. Otherwise it returns None. The new structure itself can retain heterogeneous inputs; admitting those combinations is an explicit extension assumption, not a consequence asserted by the old kernel.

Boundary inputs and nested fibers remain unsupported in this adapter. The original operator still supports its original BOUNDARY cases in the unchanged kernel. Composition of FIBER nodes is also unsupported rather than silently flattened.

## Operations on retained roles

The existing factor dual action is extended in three explicitly declared ways:

- `dual_all` toggles both roles.
- `dual_base` and `dual_fiber` toggle only the specified role.
- `dual_component` requires both a role and the intrinsic class already defined in factor-v1.

Role actions are involutions and commute across roles. Applying both role actions equals global duality. A component action in the base preserves the fiber exactly. The roles are structural selectors; no domain data determines them.

These role actions are new rules of the experimental dialect. They are not claimed to be implicit in the original scalar `op_dual`, which cannot independently address the two roles.

## Compatibility and a useful witness

Tests compare all pairs drawn from the original level-3 CYCLE states, and bases formed by self-products of each such state, against `op_fiber`. Every tested old admissible case gives the same scalar output, and old inadmissible cases have no legacy projection. This does not certify every conceivable input or the unimplemented BOUNDARY path.

Two fiber structures can have the same old BUNDLE signature while differing in base occupancy, because the old output takes occupancy from the fiber. The new representation retains base occupancy. A class action can consequently distinguish those bases afterward. This demonstrates an operationally usable distinction, not just a second provenance label.

## Paired structural experiment

Run:

```bash
python3 scripts/fiber-expansion.py --max-base-factors 3
python3 -m unittest discover -s test -p 'test_fiber_kernel.py' -v
```

Both arms use the same admitted recurrence seeds 0, 2, 3, 4. The baseline arm permits only old-compatible scalar outputs; the extended arm retains heterogeneous structures. The factor stage saturates first, then every ordered eligible base/fiber pair is enumerated, then closure under all role actions is checked. Every output of a role action must already occur in that enumerated space.

| Maximum base factors | Compatible FIBER states | Heterogeneous FIBER states |
| --- | ---: | ---: |
| 1 | 8 | 64 |
| 2 | 16 | 352 |
| 3 | 24 | 1,312 |

The count is independently checked as eight singleton fibers times the number of factor bases: `8 * (binomial(8+B, B)-1)`. The compatible arm has `8B` FIBER states. This growth follows from the declared Cartesian construction and is not an unexplained discovery.

At bound three, the full extended subexperiment has 164 FACTORS nodes, 1,312 FIBER nodes and four recurrence seeds: 1,480 nodes in total. All 9,968 distinct applications replay successfully. The compatible arm has 52 nodes and 116 applications. All compatible states are contained in the extended run.

Results and two complete example backtraces are frozen in `audit/fiber-adapter-v1-20260906.json`. Source hashes pin both experimental kernel modules. Fiber inputs stay ordered in event identity; commutative normalization applies only to compose. The graph validator rejects reversed fiber inputs with unchanged output, missing co-inputs, false output hashes/signatures, premature observations and unsupported versions.

The replay uses the operator implementation itself. Independent checks are the unchanged original-operator comparisons, algebraic laws and Cartesian state-count formula. Stabilizing actions do not establish their own seed ancestry, and no confluence or domain claim is inferred from their counts.

Seven adapter tests, nine factor-v1 tests and fifteen original-kernel tests pass. No domain interpretation was supplied to the experiment. No production exporter, database, UI or native DIRECT/INHERITED classification was changed. The next unimplemented integration is boundary, whose representation and laws must be specified separately.
