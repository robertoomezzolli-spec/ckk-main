# FÄCHER scale test — Level 6

## 1. Bottleneck

The unchanged historical expander snapshots the full prior pool at every
level, executes four binary operators on every ordered pair, recursively
rebuilds `Struct.sig()` tuples, and copies those tuples into every derivation.
At Level 5 it used 6,155,042,816 bytes peak RSS, took 23.30 s, held 100,813
states and 172,287 raw derivation events. Level 6 would schedule
10,163,260,969 ordered pairs and 40,653,043,876 binary dispatches.

The instrumented Level-4 reference profile attributes 36,415,087 live bytes
and 602,006 allocations directly to `grammar.py:24`, the recursive `sig()`
construction. Reachable heap size was 14,813,277 bytes for the state pool and
37,496,639 bytes for copied provenance. `sig()` consumed 2.004 s, versus 0.246
s for all operator calls and 0.0057 s for dictionary membership/equality.
`structural_sig()` consumed zero because this historical experiment does not
use the quotient identity.

`op_product` is the blow-up source. Level 6 has 249,852,948 valid products,
1,243,668 fibers, 144,200 degenerations, and 145,096 exclusions.

## 2. Optimization architecture

- exact state interning by scalar fields plus canonical direct-part IDs;
- state/provenance separation in SQLite;
- frontier-only semi-naive evaluation;
- streamed, indexed, operator-valid candidate joins;
- unordered pairs only for the proven-commutative `op_product`;
- phase cursor checkpoint every bounded batch;
- exact ranked product segments for the 249.85 million Level-6 products;
- reversible virtual state IDs and implicit `(parents, op_product, child)`
  provenance;
- 900 MB peak-RSS watermark, 2 GB free-disk watermark, 900 s wall budget;
  node and derivation caps unset.

No grammar file, operator, seed, dimension rule, or admissibility predicate was
changed.

## 3. Levels 1–5 equivalence proof

Reference and new engine independently reconstructed every full historical
`Struct.sig()` tuple and normalized `Derivation.event_key()`. Cardinalities and
sorted SHA-256 content manifests match at every level. Level 5 matches at:

- states: 100,813,
  `4d2212cfc2e275abdb59d3fad58d0fa7d1dd12be7bbd3d6e1378cde94fc40df6`;
- derivation classes: 102,243,
  `1b7d7377c9b037cb7ec420aca30e79a4604264ef7fdbe45dc696b278ad5745a5`;
- max dimension: 16;
- every per-operator event count and manifest.

The compact rows also reconstruct the raw replay totals exactly:
5, 48, 443, 4,864, 172,287 for Levels 1–5. Thus scheduler repetition and
commutative reversal were compressed, not discarded.

## 4. Level 6 result

Level 6 completed:

- total states: 251,844,690;
- new states: 251,743,877;
- unique derivation classes: 251,862,211;
- raw historical replay/orientation events: 501,881,798;
- max dimension: 32;
- peak RSS: 101.504 MiB;
- operator phase time: 313.445 s;
- checkpoint database: 775,831,552 bytes.

The old engine's Level-5 peak was 5.732 GiB; the new engine completed Level 6
at 0.099 GiB peak.

## 5. Highest completed level

Level 6. The requested Level-8 continuation attempted Level 7 and stopped
before mutating it. Level 6 remains restartable and intact.

## 6. Growth table

`Derivations` are cumulative canonical classes. `Logical pairs` is the old
ordered Cartesian pair space. `Scheduled` includes streamed unary and valid
binary operator applications. `Canonical duplicates` excludes old/old replays
and product reversal; `raw duplicates` shows what the reference scheduler
would generate before deduplication in that level.

| Level | Total states | New states | Max dim | Derivations | Logical pairs | Scheduled | Canonical duplicates | Raw duplicates | Peak GiB | Wall s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 15 | 5 | 1 | 5 | 100 | 70 | 0 | 0 | 0.016 | 0.002 |
| 2 | 53 | 38 | 2 | 43 | 225 | 59 | 0 | 5 | 0.016 | 0.008 |
| 3 | 372 | 319 | 4 | 371 | 2,809 | 482 | 9 | 76 | 0.017 | 0.040 |
| 4 | 3,561 | 3,189 | 8 | 3,685 | 138,384 | 4,545 | 125 | 1,232 | 0.018 | 0.426 |
| 5 | 100,813 | 97,252 | 16 | 102,243 | 12,680,721 | 110,079 | 1,306 | 70,171 | 0.062 | 13.151 |
| 6 | 251,844,690 | 251,743,877 | 32 | 251,862,211 | 10,163,260,969 | 252,066,676 | 16,091 | 249,965,634 | 0.099 | 313.445 |

The ratios of cumulative state counts are 3.53, 7.02, 9.57, 28.31, and
2,498.14. There is no stable exponential ratio. The governing empirical law
is group-partitioned quadratic pair formation. The exact Level-7 product term
alone is 5,925,802,394,666,872 pairs.

## 7. Maximum-dimension witness

The exact backtrace is:

```text
L1  state 11         dim 1   op_close
L2  state 30         dim 2   op_product(11, 11)
L3  state 173        dim 4   op_product(30, 30)
L4  state 1754       dim 8   op_product(173, 173)
L5  state 62374      dim 16  op_product(1754, 1754)
L6  state -60355509  dim 32  op_product(62374, 62374)
```

The last state is virtual segment 5, rank 53,066,780, and is individually
reconstructable. Doubling is directly encoded by `op_product`'s
`dim=a.dim+b.dim` on a maximal self-product. It is not an emergent invariant.

## 8. Operator explosion breakdown

New Level-6 state contributions:

| Operator | Attempted | New | Duplicates | Share of all new states |
|---|---:|---:|---:|---:|
| op_product | 249,852,948 | 249,852,948 | 0 | 99.2489% |
| op_fiber | 1,243,668 | 1,239,556 | 4,112 | 0.4924% |
| op_exclude | 145,096 | 145,096 | 0 | 0.0576% |
| op_degenerate | 144,200 | 144,200 | 0 | 0.0573% |
| op_dual | 97,252 | 92,045 | 2,723 | 0.0366% |
| op_weight | 97,252 | 88,100 | 0 | 0.0350% |
| op_winding | 97,252 | 88,100 | 0 | 0.0350% |
| op_boundary | 97,252 | 87,684 | 0 | 0.0348% |
| op_filter | 97,252 | 3,600 | 0 | 0.0014% |
| op_fill | 97,252 | 2,548 | 9,256 | 0.0010% |
| op_close | 97,252 | 0 | 0 | 0% |

## 9. Structural stabilization analysis

The frontier kind set reaches seven generated kinds at Level 3 and no kind
appears or disappears through Level 6. All operators first appear by Level 3.
Immediate `(operator,input kinds,output kind)` motifs grow 2, 11, 33, 37,
39, 39 and therefore plateau at Level 5.

That plateau is not closure. Provenance-free scalar quotient classes grow
15, 52, 204, 604, 1,403, 2,878; Level 6 adds 1,475 new signatures. Confluent
states grow to 17,435, dual/reversible two-cycles to 3,035, and 2,824 quotient
classes contain multiple provenance-bearing histories. No reachable kind
disappears. Raw and quotient state growth do not terminate or become periodic.

The self-product witness proves structural nontermination: every admissible
cycle/product `X` produces a distinct `op_product(X,X)` with doubled dimension.

## 10. Provenance analysis

At Level 6, 251,844,690 historical states occupy only 2,878 scalar structural
classes. The largest class (PRODUCT, dimension 16, order 0, multiplicity 1,
dual 0) has 7,650,979 distinct histories; the same multiplicity occurs for
orders 2, 3, and 4.

Therefore `same structural_sig + different provenance` means the same quotient
state but a distinct historical derivation-bearing state. Separately, 17,435
full historical states are true confluences with more than one distinct
operator event producing the identical state. Both distinctions remain
queryable; neither was optimized away.

## 11. Termination classification

**COMPUTATIONAL TERMINATION at the Level-7 frontier.** The grammar did not
terminate. Level-7 `op_product` alone has 5,925,802,394,666,872 exact pairs in
24 groups. Two 64-bit parent references per explicit edge would require at
least 94,812,838,314,669,952 bytes, versus 46,255,853,568 free bytes on the
compute host. The completed Level-6 checkpoint survives.

## 12. Final answer

Beyond Level 5, FÄCHER does not close. It undergoes group-wise quadratic
provenance explosion dominated by `op_product`, reaches 251.8 million exact
states and dimension 32 at Level 6 while using only 101.5 MiB RAM, and then
hits a computational Level-7 provenance frontier of 5.93 quadrillion product
pairs. Kinds and immediate operator motifs stabilize, but quotient signatures,
confluences, provenance histories, and dimension continue to grow.

## Reproducibility

- Remote checkpoint: `/opt/faecher-scale/run/scale.sqlite`
- Checkpoint SHA-256:
  `573eab401481bcbde57e6c1afa3d9e7fc43ac7782007a6ebee18646949c108df`
- Exact analysis: `analysis.json`
- Equivalence proof: `equivalence-proof.json`
- Reference profile: `reference-profile.json`
- Level-5 peak: `reference-level5-peak.json`
- Level-6 result: `level6.json`
- Level-8 attempt: `level8-attempt.json`
