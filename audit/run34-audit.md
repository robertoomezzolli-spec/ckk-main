# CKK Run 34 confluence audit

## Wayback point

- Git branch: `backup/pre-run34-audit-20260827-151831`
- Git tag: `pre-run34-audit-20260827-151831`
- Ausgangscommit: `7e7b3dbe2b1fc2658403b72f6a754df09813bf70`
- Working-tree stash: `bd2e5865d2cb41846b7130447890a2720b82cecd`
- Neon production branch: `br-wild-hill-awswgush`
- Neon backup branch: `br-icy-bar-aw2gv084` (`snapshot-pre-run34-audit-20260827-151831`)
- Neon parent LSN: `0/379BBF8`
- Production deployment: `6a9035de3b4e5f000812f973` (ready)

The Git references are pushed, the pre-existing untracked file was reapplied with an unchanged SHA-256, and the read-only Neon backup independently reproduced Run 34 at 276/945/196 before the audit started.

## Scope

- Mode: **READ-ONLY snapshot measurement**
- Source: `ckk-graph-v6-noselfdual-563f50e328c5-2.json`
- SHA-256: `8627e79c0b7ef61a2d989290c2250003f837590d37cb2c99fa9c31d008335a90`
- Generation: `v6-noselfdual-563f50e328c5`
- Grammar: `v6-html-no-asserted-selfdual`
- Run: `34`
- Constraint: Conservative projection of historical Run 33; excluded asserted dual=2 nodes and incident edges are not reconstructed.
- Self-duality `D(X) ≡ X`: **NOT_EVALUATED**

## Hard integrity — PASS

| Measure | Recomputed value |
|---|---:|
| Nodes | 276 |
| Edges | 945 |
| Confluences (in-degree >= 2) | 196 |
| KNOWN | 15 |
| REDISCOVERED | 2 |
| VARIANT | 129 |
| UNMATCHED | 130 |
| Dangling edges | 0 |
| Self-loops | 0 |
| Duplicate node IDs | 0 |
| dual=2 | 0 |
| Unverified self-duality claims | 0 |

The confluence count was computed from stored edge in-degree and not copied from the export summary.

## Root diversity

- diversity 1: 6 nodes
- diversity 2: 6 nodes
- diversity 3: 63 nodes
- diversity 4: 12 nodes
- diversity 5: 60 nodes
- diversity 6: 129 nodes

Root classes are reconstructed by reverse reachability to the six stored ADMITTED roots: CARRIER +1, CARRIER -1, RECURRENCE, SYMMETRY, BOUNDCOND D, BOUNDCOND N.

## Confluence quality

Audit vector: `C(X)=(root_diversity, unique_parents, paths, parent_signature_diversity, provenance_quality, semantic_risk)`.

Risk is a transparent collision-prioritization heuristic, not a physical judgment. Labels, physics catalog entries, KNOWN and REDISCOVERED status do not enter risk or ranking. Exact rules are stored in `run34-audit.json.methodology.semantic_risk_rules`.

Classification distribution:

- LOW_RISK: 21
- REQUIRES_PROVENANCE: 175

### Top 25 possible false-confluence candidates

| Rank | Node | Kind | d | Verdict | Class | Risk | Roots | Parents | Parent signatures | Paths |
|---:|---:|---|---:|---|---|---|---:|---:|---:|---:|
| 1 | 121 | CYCLE | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 31 | 31 | 91 |
| 2 | 130 | CYCLE | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 31 | 31 | 91 |
| 3 | 133 | CYCLE | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 17 | 17 | 52 |
| 4 | 46 | BUNDLE | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 15 | 15 | 267 |
| 5 | 271 | PRODUCT | 2 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 15 | 15 | 267 |
| 6 | 67 | BUNDLE | 1 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 14 | 14 | 265 |
| 7 | 292 | PRODUCT | 2 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 14 | 14 | 265 |
| 8 | 322 | PRODUCT | 3 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 14 | 14 | 112 |
| 9 | 41 | BUNDLE | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 13 | 13 | 227 |
| 10 | 266 | PRODUCT | 2 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 13 | 13 | 227 |
| 11 | 61 | BUNDLE | 1 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 12 | 12 | 275 |
| 12 | 286 | PRODUCT | 2 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 12 | 12 | 275 |
| 13 | 321 | PRODUCT | 3 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 12 | 12 | 100 |
| 14 | 327 | PRODUCT | 3 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 12 | 12 | 100 |
| 15 | 205 | WEIGHT | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 11 | 11 | 25 |
| 16 | 325 | PRODUCT | 3 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 10 | 10 | 95 |
| 17 | 200 | WEIGHT | 1 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 10 | 10 | 25 |
| 18 | 238 | BUNDLE | 2 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 9 | 9 | 55 |
| 19 | 220 | WEIGHT | 1 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 9 | 9 | 21 |
| 20 | 243 | BUNDLE | 2 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 8 | 8 | 80 |
| 21 | 237 | BUNDLE | 2 | VARIANT | REQUIRES_PROVENANCE | HIGH | 6 | 8 | 8 | 55 |
| 22 | 228 | WEIGHT | 1 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 7 | 7 | 9 |
| 23 | 241 | BUNDLE | 2 | UNMATCHED | REQUIRES_PROVENANCE | HIGH | 6 | 6 | 6 | 75 |
| 24 | 180 | INTEGER | 1 | VARIANT | REQUIRES_PROVENANCE | MEDIUM | 6 | 5 | 5 | 17 |
| 25 | 185 | INTEGER | 1 | VARIANT | REQUIRES_PROVENANCE | MEDIUM | 6 | 5 | 5 | 16 |

No candidate is declared erroneous. `REQUIRES_PROVENANCE` means the stored parent heterogeneity cannot be resolved because incoming edges retain only snapshot identifiers.

## Node 316

- Stored signature: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0
- Stored paths: 266
- In-degree / out-degree: 10 / 10
- Root diversity: 3
- Parent signature diversity: 10
- Relation to 257: 1 stored direct edge(s)
- Relation to 331: 1 stored direct edge(s)
- UNMATCHED confluence rank: 58

See `run34-node316.md` for two parent and two child levels with raw stored edges.

## Dimension chain 22 -> 76 -> 257 -> 316 -> 331

- 22 -> 76: stored; edge 7708, operator=snapshot_v6:0000, paths=1; semantics=NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER
- 76 -> 257: stored; edge 7730, operator=snapshot_v6:0024, paths=30; semantics=NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER
- 257 -> 316: stored; edge 7779, operator=snapshot_v6:0089, paths=210; semantics=NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER
- 316 -> 331: stored; edge 8109, operator=snapshot_v6:0513, paths=70; semantics=NOT_RECONSTRUCTIBLE_FROM_SNAPSHOT_IDENTIFIER

The audit does not reconstruct `op_close`, `op_product`, or any other operator from `snapshot_v6:*` identifiers.

## Dimension transitions

| Transition | Edges | Sources | Targets | Source coverage | Target coverage | Avg fan-out | Avg fan-in |
|---|---:|---:|---:|---:|---:|---:|---:|
| d0->d1 | 96 | 6 | 96 | 0.285714 | 0.611465 | 16 | 1 |
| d1->d2 | 87 | 31 | 16 | 0.197452 | 0.231884 | 2.806452 | 5.4375 |
| d2->d3 | 17 | 11 | 8 | 0.15942 | 0.533333 | 1.545455 | 2.125 |
| d3->d4 | 1 | 1 | 1 | 0.066667 | 0.071429 | 1 | 1 |

All 25 measured d0..d4 transitions are in `run34-dimension-transitions.csv`. No dimensional transition is interpreted physically.

## Duality

- dual=0: 208
- dual=1: 68
- dual=2: 0
- `D(D(X))=X`: **NOT_VERIFIABLE_FROM_SNAPSHOT**
- `D(X) ≡ X`: **NOT_EVALUATED**

Stored-signature partners are listed only as candidates. No semantic `op_dual` provenance survives in the snapshot, so involution is not claimed.

## KNOWN / REDISCOVERED controls

- KNOWN: 15
- REDISCOVERED: 2
- Node 314 stored claim: 3D quantum Hall / Chern vector over T³
- Node 331 stored claim: 4D quantum Hall / second Chern number

These are stored Run-34 claims only; this audit performs no external-physics validation.

## UNMATCHED

- Count: 130
- Confluences: 74
- Non-confluences: 56
- Node 316 objective structural rank: 58

Full groupings and raw candidates are in the JSON and CSV outputs.

## Provenance limitation

- Semantic operator names: 0
- `snapshot_v6:*` identifiers: 945
- No usable operator provenance: 0

The conservative Run-34 projection stores synthetic snapshot_v6:* edge identifiers. Historical operator semantics cannot be reconstructed from this snapshot and are never inferred by this audit.

## Change safety

- Nodes: 276 -> 276
- Edges: 945 -> 945
- Run: 34 -> 34
- Generation: v6-noselfdual-563f50e328c5 -> v6-noselfdual-563f50e328c5
- Graph changed: false
