# FAECHER unbounded-dimension experiment

## Scope

This is a fresh structural expansion of the current Python grammar. It does
not query the physics catalog, reinterpret Run 34, infer operators from output
kinds, or collapse dimensions. The exact built-in seeds and exact registered
operators are used. `MAXDIM` is `None`; optional finite dimensions are staged
controls only.

Grammar SHA-256:
`afd52bc69b014d418826c400d2eb5e159ca41fb3e60fee68f8da90dcf18e89da`

Runner SHA-256:
`d124b50543bf2b9683a3fbd273253fdae6994247be2fdfc166339b597146e0dd`

## Compute limits

Every run used the same limits:

- wall clock: 30 seconds
- peak RAM: 1,024 MiB
- structural states: 20,000
- unique derivation events: 250,000

These are COMPUTE LIMITS. They are not structural or dimensional limits.

## Run outcomes

| Run | Termination class | Cause | Seconds | States | Events | Maximum observed dimension | Peak MiB | Pending |
|---|---|---|---:|---:|---:|---:|---:|---:|
| stage 5 | STAGED_BOUND_SATURATION | queue exhausted | 2.733 | 2,458 | 10,709 | 5 | 32.9 | 0 |
| stage 6 | STAGED_BOUND_SATURATION | queue exhausted | 3.754 | 2,890 | 13,037 | 6 | 35.8 | 0 |
| stage 8 | STAGED_BOUND_SATURATION | queue exhausted | 6.297 | 3,754 | 17,981 | 8 | 40.7 | 0 |
| stage 10 | STAGED_BOUND_SATURATION | queue exhausted | 9.513 | 4,618 | 23,357 | 10 | 48.2 | 0 |
| stage 12 | STAGED_BOUND_SATURATION | queue exhausted | 13.387 | 5,482 | 29,165 | 12 | 54.2 | 0 |
| stage 16 | STAGED_BOUND_SATURATION | queue exhausted | 22.862 | 7,210 | 42,077 | 16 | 65.7 | 0 |
| stage 24 | COMPUTATIONAL_TERMINATION | wall clock | 30.008 | 9,849 | 65,881 | 24 | 89.9 | 1,897 |
| unbounded | COMPUTATIONAL_TERMINATION | wall clock | 30.002 | 15,933 | 184,819 | 256 | 209.1 | 7,829 |

Finite-stage queue exhaustion proves saturation only for the deliberately
bounded control grammar. It does not prove termination of the unbounded
grammar. Stage 24 and the unbounded run stopped with work still pending.

## Complete saturated per-dimension record through stage 16

`new states` counts distinct structural signatures at that dimension.
Confluences require at least two distinct provenance event keys. Cycles are
strongly connected components in the unary event graph; binary arity is never
projected into false graph edges.

| dim | new states | first new kinds | transitions | confluences | unary cycles | product transitions | kinds disappearing |
|---:|---:|---|---:|---:|---:|---:|---|
| 0 | 370 | BOUNDARY, BUNDLE, CARRIER, FILTER, INTEGER, RECURRENCE, SYMMETRY, WEIGHT | 1,177 | 288 | 108 | 0 | none |
| 1 | 432 | CYCLE | 1,756 | 356 | 144 | 0 | CARRIER, RECURRENCE, SYMMETRY |
| 2 | 432 | PRODUCT | 1,896 | 360 | 144 | 144 | CYCLE |
| 3 | 432 | none | 1,968 | 360 | 144 | 216 | none |
| 4 | 432 | none | 2,112 | 360 | 144 | 360 | none |
| 5 | 432 | none | 2,184 | 360 | 144 | 432 | none |
| 6 | 432 | none | 2,328 | 360 | 144 | 576 | none |
| 7 | 432 | none | 2,400 | 360 | 144 | 648 | none |
| 8 | 432 | none | 2,544 | 360 | 144 | 792 | none |
| 9 | 432 | none | 2,616 | 360 | 144 | 864 | none |
| 10 | 432 | none | 2,760 | 360 | 144 | 1,008 | none |
| 11 | 432 | none | 2,832 | 360 | 144 | 1,080 | none |
| 12 | 432 | none | 2,976 | 360 | 144 | 1,224 | none |
| 13 | 432 | none | 3,048 | 360 | 144 | 1,296 | none |
| 14 | 432 | none | 3,192 | 360 | 144 | 1,440 | none |
| 15 | 432 | none | 3,264 | 360 | 144 | 1,512 | none |
| 16 | 360 | none | 3,024 | 288 | 144 | 1,656 | BOUNDARY |

Dimension 16 is the staged control boundary. Its missing 72 BOUNDARY families
are a top-edge artifact: `op_boundary` generates dimension 16 from structures
at dimension 17, which the stage-16 control forbids. The same artifact appears
only at the top dimension of every fully saturated finite stage. All interior
dimensions 2 through 15 have the same 432 structural signatures, six kinds,
360 confluent states and 144 unary cycle components.

The complete per-dimension records for all observed dimensions, including the
partial unbounded range through 256, are stored in the corresponding summary
JSON files. Every full event and structural signature is in the compressed
provenance artifact for that run.

## Growth classification

- Structural kinds change at dimensions 1 and 2 only. No new kind first
  appears at dimension 3 or above in any saturated control.
- Interior state growth stabilizes at 432 new signatures per dimension.
  Across the saturated controls, total states follow `N(D) = 432D + 298`.
- Product derivation counts grow with the number of compatible dimension
  partitions. Per-dimension transitions therefore grow approximately linearly
  and total provenance grows approximately quadratically.
- The small alternating increment in product-event counts is a partition
  parity effect. It does not change the structural state families.
- Unary cycles persist at every interior dimension. They are the explicit
  `op_dual` involutions, not global termination of the expansion.

## Constructive nontermination

For any admitted recurrence order, let

`C = op_close(RECURRENCE)`.

`C` is a dimension-one `CYCLE`. Define `P(1) = C` and

`P(d + 1) = op_product(P(d), C)`.

The inputs retain equal order, symmetry, boundary condition and dual branch,
so the registered product operator remains applicable. Its output dimension is
`d + 1`. Dimension belongs to `structural_sig()`, hence every `P(d + 1)` is a
new structural signature. This supplies an infinite chain independently of
the empirical staged runs.

Therefore the unbounded grammar cannot reach global signature exhaustion or a
global fixpoint while this operator and seed remain present. Local dual cycles
do not halt the product chain.

## Provenance integrity

All eight compressed artifacts passed these checks:

- every non-seed state is the output of at least one recorded operator event;
- every event input and output exists in the same artifact;
- event keys are unique, with commutative product inputs normalized;
- artifact state/event counts equal their summaries;
- SHA-256 digests equal the recorded artifact hashes.

No result depends on snapshot-derived cosmetic fields or inferred operator
names.

## Conclusion

Dimension 4 has no intrinsic structural significance in this grammar. It is
an ordinary interior member of a dimension-stable family. The grammar proceeds
naturally through 5, 6, 7 and beyond; the unbounded timed run generated a valid
signature at dimension 256 before its compute budget expired.

There is no STRUCTURAL TERMINATION. The observed stops are either saturation of
an explicitly bounded control or COMPUTATIONAL TERMINATION. The unbounded
grammar continues indefinitely by repeated registered product composition.
