# Where the current fan can expand its expressivity

This audit asks what the domain-neutral grammar cannot currently distinguish or compose. It does not require the generator to know physics, biology, computation or agency. The pinned kernel is unchanged.

Reproduce with `python3 scripts/audit-expansion-bottlenecks.py`. The accompanying JSON records concrete witnesses and observations over 1,403 states and 4,491 unique applications at level 5. Source inspection establishes the invariants below beyond that finite run.

| Boundary | Evidence | What more dimensions cannot solve |
| --- | --- | --- |
| Recurrence orders | Seeds supply 0, 2, 3, 4; operators preserve order or require equal input orders. | No order 5 or 6 can arise with this registry and these seeds. |
| Heterogeneous composition | Product of order-2 and order-3 cycles is rejected, as is a mixed-dual product. | Compatible composition needs a representation for distinct factor properties. |
| Factor properties | Product of occupancy-1 and occupancy-minus-1 cycles has the same compact signature as product of two occupancy-unspecified cycles. | The different inputs survive in provenance, but current operators cannot use their distinction afterward. |
| Symmetry action | The two anti=False canonical symmetry seeds participate in no application; op_degenerate requires anti=True. | These admitted distinctions have no acting operator in the current registry. |
| Boundary conditions | All canonical seeds have bc=None; every operator preserves that value. | op_boundary changes kind and dimension; it does not create a boundary-condition value. |

These are expressivity boundaries, not automatically defects. In particular, equal compact signatures are deliberately quotiented. A different factorization history alone does not justify a different structural state. An extension needs an intrinsic distinction and a reason later operations should depend on it.

## First candidate: retain factor properties in heterogeneous composition

The strongest concrete starting point is the existing product guard: its own source comment says a mixed dual pair must be rejected until a factor-level carrier exists. The analogous issue occurs for mixed recurrence orders.

A separate experimental representation could retain canonical structural factor descriptors, keeping derivation-event identity separate. Before implementing its generator, specify whether factors are ordered, how associativity works, what duality acts on, and which existing scalar outputs remain valid projections. Do not silently combine recurrence orders with lcm: that requires a chosen interpretation of the recurrence action.

The decisive test is not a larger node count. Predeclare a downstream operation that needs a factor distinction, show why the old representation cannot support it, then show the new representation preserves it and replays all inputs. Controls must distinguish reassociation or duplicate histories from genuinely different factor structures. New results must not be certified by the verifier pinned to the old grammar.

## DIRECT and inherited properties

The JSON also records per-operator equality of output fields with input fields. This is diagnostic only, not the application's native DIRECT/INHERITED classification. For example, a constant assignment or max operation can equal an input without being a simple copy. Causal classification must come from the actual operator semantics and full co-input trace.

## Limits

No proposed primitive was admitted, no production data was changed, and no domain match or natural-law prediction is claimed. This delivers executable witnesses of current limits and a concrete priority for a separately specified extension experiment.
