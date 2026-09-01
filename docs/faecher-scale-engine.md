# FÄCHER disk-backed scale engine

`ckk_snapshot/ckk/gen/stream_expand.py` expands the historical,
provenance-bearing `Struct.sig()` state space without keeping recursive object
trees or candidate matrices in RAM. It does not modify `grammar.py`, the seed
set, the registered operator list, or operator semantics.

## Exact representation

A material state is interned by its ten historical scalar fields plus the
multiset of canonical IDs of its direct parts. This is equivalent to
`Struct.sig()` equality by induction over the finite state tree. The SQLite
key stores the complete tuple; no probabilistic digest participates in state
identity. Derivations are separate rows:

```text
(operator, input_a, input_b, output, first_level)
```

`first_level` is enough to reconstruct every redundant historical replay. For
`op_product`, unequal inputs have two ordered reference replays; the canonical
event remains one commutative derivation, matching `Derivation.event_key()`.

Large product frontiers use exact ranked segments. A segment records one
compatibility group and represents every unordered pair with at least one
frontier member. `state_id = virtual_start - rank(i,j)` is reversible; loading
that ID un-ranks its parents and invokes the registered `op_product` function.
The small forced-segment regression reconstructs the complete Level-2
reference set and provenance count.

## Streaming and checkpoints

Unary candidates stream by frontier ID. Binary SQL joins contain only guards
already present in the corresponding registered operator; the operator is
still invoked for every scheduled row. Unknown future operators fall back to
the full ordered semi-naive join. Only `op_product` uses unordered inputs,
because its implementation is symmetric and its historical parts are sorted.

Each operator phase commits a bounded batch together with its lexicographic
cursor and counters. SQLite uses WAL and `synchronous=FULL`. A restart resumes
the incomplete phase; completed levels and earlier batches survive. Resource
limits are operational only:

- wall-clock seconds;
- peak-RSS watermark;
- minimum free-disk watermark;
- optional node/derivation caps (unset in the scale run).

No dimension limit exists, and a resource stop is always reported as
`COMPUTATIONAL_TERMINATION`.

## Commands

The main runner is `scripts/faecher-scale.py`. Supporting tools are:

- `scripts/faecher-reference-profile.py`: unchanged Cartesian reference
  profiler;
- `scripts/faecher-equivalence.py`: full historical signature and provenance
  manifests;
- `scripts/faecher-analyze-scale.py`: longitudinal quotient, confluence,
  cycle, operator, and maximum-dimension witness analysis.

The completed experiment artifacts are in `audit/faecher-scale/`. The 776 MB
SQLite checkpoint is intentionally not committed; its path and SHA-256 are in
the report.
