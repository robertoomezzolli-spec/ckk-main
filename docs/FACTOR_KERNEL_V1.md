# Experimental factor kernel v1

This implements the heterogeneous-composition candidate identified in `audit/expansion-bottlenecks-20260906.md`. It is a separate executable structural dialect alongside the original kernel. The original `grammar.py`, its seeds, exporter, verifier, database and presentation are unchanged.

## Exact scope

The new kernel represents compositions of dimension-one CYCLE factors. Each factor carries the existing ten scalar fields. A node is a canonical nonempty multiset of factors. Nested composition is flattened; factors are sorted; repeated factors are retained. Operator history, labels, domain annotations and source names are not structural identity.

The algebra has no maximum dimension. The experiment runner limits the number of factors, plus time, nodes, events and expansion levels. It never equates a budget stop with global saturation.

## Declared rules

| Operator | Rule | Origin of properties |
| --- | --- | --- |
| close | Lift a recurrence of order n to one CYCLE factor of order n, using the existing close rule. | Order is copied; kind and dimension are assigned by close. |
| compose | Multiset union of the two input factor collections. | Every factor descriptor is retained; the composition relation is introduced here. |
| dual_all | Toggle the 0/1 dual marker on every factor. | Other scalar properties are copied. |
| dual_component | Toggle the dual marker on every factor belonging to a selected intrinsic class. A class comprises all factor fields except dual. | The selected marker changes; other fields and other classes are copied. |

The selected class is determined from the input structure. There is no arbitrary factor index and no selection by narrative meaning. Identical copies cannot be distinguished through provenance. Class membership remains stable under duality, making repeated action an involution. Actions on different classes commute.

These rules are explicit modeling choices. Associativity, commutativity and class-wise action are not claimed to have been discovered by the old kernel. There is no unit, cancellation, reduction of recurrence orders, new order seed, or claim that a mixed-order product has order equal to an lcm. Recurrence orders remain 0, 2, 3, 4 in the benchmark.

## Compatibility and useful new distinction

`legacy_projection` maps a factor collection to the old scalar CYCLE/PRODUCT signature only when its factors have compatible order, symmetry, boundary condition and dual marker. Otherwise it returns `None`. This projection is explicitly lossy, not an equivalence of full structures.

The compatibility test compares every pair of CYCLE states from the original level-3 expansion with the original `op_product`, and compares global duality with the original `op_dual`.

A concrete witness uses two products that previously shared one compact signature:

- factors with occupancy 1 and -1;
- two factors whose occupancy is unspecified.

Their histories were already distinguishable. Now their structural descriptors differ, so the new class action can toggle only the occupancy-1 factor in the first product. That same action is inadmissible in the second product. Thus a retained difference affects a downstream operation instead of merely increasing the number of labels.

## Experiment and validation

Run:

```bash
python3 scripts/factor-expansion.py --max-factors 4
python3 -m unittest discover -s test -p 'test_factor_kernel.py' -v
python3 -m unittest discover -s test -p 'test_generator_core.py' -v
```

The paired benchmark is deliberately limited to recurrence/close/composition/duality. It is not a comparison against the entire 11-operator grammar. Both arms use the same four admitted recurrence seeds, factor bound and candidate operations. The baseline arm restricts outputs to the old homogeneous compatibility conditions.

| Factor budget | Compatible factor states | Heterogeneous factor states |
| --- | ---: | ---: |
| 2 | 16 | 44 |
| 3 | 24 | 164 |
| 4 | 32 | 494 |

The counts agree with an independent combinatorial check: there are eight available atomic descriptors (four orders and two dual markers), yielding `binomial(8 + B, B) - 1` nonempty multisets of size at most B. The baseline yields `8B`. The growth is therefore explained by the chosen algebra; it is not an unexpected empirical discovery.

At budget four, the extension records 3,588 unique applications and 498 seed-rooted nodes including four recurrence seeds. The baseline records 100 applications and 36 nodes including seeds. All baseline states are retained. Every application is replayed and checked for earlier availability of every co-input. Three example backtraces are included in `audit/factor-expansion-v1-20260906.json`.

The graph dialect uses full factor signatures, content hashes and a source-hash-pinned operator version. Observation level is excluded from application identity. Commutative input reversal does not create a second compose application. The replay validator rejects unknown operators, mismatched versions, false outputs, missing ancestors, unadmitted seeds and duplicate events. The replay uses the same operator implementation; independent checks come from the algebraic identities, combinatorial counts and original-kernel projection comparisons.

## Fixed points and provenance

Under the explicitly declared multiset equivalence, a pair containing X and its toggled counterpart is invariant under global toggling. There are 14 such factor states through budget four. This is a structural fixed-point result of this dialect only. No physical self-duality or legacy `dual=2` assertion follows.

Stabilizing applications are recorded as operator applications even when output equals input. Their input must already have a seed-rooted derivation. They cannot establish their own existence. No confluence or discovery claim is inferred from these stabilizers or from the redundancy between global and component action.

The trace records operators, all input identities, parameters, output identity and observation level. The property-origin table above documents their semantics; it does not silently reuse the presentation's unverified DIRECT/INHERITED verdict vocabulary.

## Remaining work

This is a working isolated extension with tests and a runner. Bundle/fiber, boundary, weight/filter and the unused symmetry actions are not lifted into this dialect. The existing scientific API intentionally does not accept its separate payload format. Neither the full fan nor the production UI has been switched to this representation. Those integrations need their own structural rules and compatibility checks.

No domain catalog, biological mechanism, physical formula, agency target or external research result enters generation. The only imports in the new kernel are JSON and hashing support.
