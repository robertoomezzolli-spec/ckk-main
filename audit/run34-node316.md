# Run 34 — Node 316 deep audit

Source generation: `v6-noselfdual-563f50e328c5`  
Run: `34`  
Projection constraint: Conservative projection of historical Run 33; excluded asserted dual=2 nodes and incident edges are not reconstructed.  
Self-duality: **NOT_EVALUATED**

## Stored node

- ID: 316
- Signature: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0
- Verdict: UNMATCHED
- Lifecycle: GENERABLE
- Paths (stored node field): 266
- In-degree / out-degree: 10 / 10
- Unique parents / children: 10 / 10
- Root classes: CARRIER +1, CARRIER -1, RECURRENCE
- Root diversity: 3
- Parent signature diversity: 10
- Incoming / outgoing stored edge path sums: 423 / 180

No physical interpretation is added. Edge operators are reproduced exactly as stored.

## Direct parents

- 76: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=6; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 77: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=1; paths=4; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 79: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=2; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 80: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=2; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 81: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=1; paths=3; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 82: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=1; paths=3; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 257: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=106; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 258: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=1; paths=17; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 260: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=15; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 261: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=15; roots=[CARRIER +1, CARRIER -1, RECURRENCE]

### Incoming edges

- edge 7778: 76 -> 316; operator=snapshot_v6:0088; paths=38
- edge 7779: 257 -> 316; operator=snapshot_v6:0089; paths=210
- edge 7802: 77 -> 316; operator=snapshot_v6:0112; paths=57
- edge 7879: 79 -> 316; operator=snapshot_v6:0204; paths=19
- edge 7886: 80 -> 316; operator=snapshot_v6:0211; paths=19
- edge 8107: 258 -> 316; operator=snapshot_v6:0510; paths=14
- edge 8114: 260 -> 316; operator=snapshot_v6:0522; paths=14
- edge 8115: 261 -> 316; operator=snapshot_v6:0523; paths=14
- edge 8193: 81 -> 316; operator=snapshot_v6:0620; paths=19
- edge 8195: 82 -> 316; operator=snapshot_v6:0622; paths=19

## Parents at distance 2

- 11: kind=CARRIER, dim=0, recurrence_order=0, factor=—, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=1; roots=[CARRIER +1]
- 12: kind=CARRIER, dim=0, recurrence_order=0, factor=—, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=1; roots=[CARRIER -1]
- 22: kind=RECURRENCE, dim=0, recurrence_order=0, factor=—, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=1; roots=[RECURRENCE]
- 76: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=6; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 77: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=1; paths=4; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 79: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=2; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 80: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=2; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 81: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=1; paths=3; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 82: kind=CYCLE, dim=1, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=1; paths=3; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 257: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=106; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 258: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=1; paths=17; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 260: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=15; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 261: kind=PRODUCT, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=15; roots=[CARRIER +1, CARRIER -1, RECURRENCE]

### Distance-2 edge layer

- edge 7708: 22 -> 76; operator=snapshot_v6:0000; paths=1
- edge 7737: 77 -> 76; operator=snapshot_v6:0033; paths=3
- edge 7973: 81 -> 76; operator=snapshot_v6:0338; paths=1
- edge 7977: 82 -> 76; operator=snapshot_v6:0342; paths=1
- edge 7712: 76 -> 77; operator=snapshot_v6:0004; paths=2
- edge 7759: 79 -> 77; operator=snapshot_v6:0063; paths=1
- edge 7763: 80 -> 77; operator=snapshot_v6:0068; paths=1
- edge 7726: 76 -> 79; operator=snapshot_v6:0020; paths=2
- edge 7727: 11 -> 79; operator=snapshot_v6:0021; paths=2
- edge 7728: 76 -> 80; operator=snapshot_v6:0022; paths=2
- edge 7729: 12 -> 80; operator=snapshot_v6:0023; paths=2
- edge 7798: 77 -> 81; operator=snapshot_v6:0108; paths=3
- edge 7799: 11 -> 81; operator=snapshot_v6:0109; paths=3
- edge 7800: 77 -> 82; operator=snapshot_v6:0110; paths=3
- edge 7801: 12 -> 82; operator=snapshot_v6:0111; paths=3
- edge 7730: 76 -> 257; operator=snapshot_v6:0024; paths=30
- edge 7772: 77 -> 257; operator=snapshot_v6:0080; paths=45
- edge 7774: 79 -> 257; operator=snapshot_v6:0084; paths=15
- edge 7776: 80 -> 257; operator=snapshot_v6:0086; paths=15
- edge 7956: 258 -> 257; operator=snapshot_v6:0311; paths=1
- edge 8110: 81 -> 257; operator=snapshot_v6:0514; paths=15
- edge 8112: 82 -> 257; operator=snapshot_v6:0516; paths=15
- edge 7767: 257 -> 258; operator=snapshot_v6:0073; paths=15
- edge 8084: 260 -> 258; operator=snapshot_v6:0481; paths=1
- edge 8089: 261 -> 258; operator=snapshot_v6:0487; paths=1
- edge 7891: 257 -> 260; operator=snapshot_v6:0216; paths=15
- edge 7892: 11 -> 260; operator=snapshot_v6:0217; paths=15
- edge 7893: 257 -> 261; operator=snapshot_v6:0218; paths=15
- edge 7894: 12 -> 261; operator=snapshot_v6:0219; paths=15

## Direct children

- 231: kind=BOUNDARY, dim=2, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=5; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 314: kind=BUNDLE, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=70; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 315: kind=INTEGER, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=5; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 317: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=1; paths=5; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 319: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=5; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 320: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=5; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 321: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=S+a, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=100; roots=[CARRIER +1, CARRIER -1, RECURRENCE, SYMMETRY, BOUNDCOND D, BOUNDCOND N]
- 322: kind=PRODUCT, dim=3, recurrence_order=0, factor=2pi, symmetry=S-a, sq=null, anti=null, multiplicity=2, boundary_condition=null, occupancy=null, dual=0; paths=112; roots=[CARRIER +1, CARRIER -1, RECURRENCE, SYMMETRY, BOUNDCOND D, BOUNDCOND N]
- 328: kind=WEIGHT, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=5; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 331: kind=PRODUCT, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=260; roots=[CARRIER +1, CARRIER -1, RECURRENCE]

### Outgoing edges

- edge 7961: 316 -> 315; operator=snapshot_v6:0322; paths=5
- edge 7962: 316 -> 231; operator=snapshot_v6:0323; paths=5
- edge 7963: 316 -> 328; operator=snapshot_v6:0324; paths=5
- edge 7964: 316 -> 317; operator=snapshot_v6:0325; paths=5
- edge 8109: 316 -> 331; operator=snapshot_v6:0513; paths=70
- edge 8362: 316 -> 321; operator=snapshot_v6:0877; paths=5
- edge 8364: 316 -> 322; operator=snapshot_v6:0879; paths=5
- edge 8366: 316 -> 319; operator=snapshot_v6:0881; paths=5
- edge 8368: 316 -> 320; operator=snapshot_v6:0883; paths=5
- edge 8370: 316 -> 314; operator=snapshot_v6:0885; paths=70

## Children at distance 2

- 313: kind=BOUNDARY, dim=3, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=1; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 329: kind=BUNDLE, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=14; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 330: kind=INTEGER, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=1; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 332: kind=PRODUCT, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=1; paths=1; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 334: kind=PRODUCT, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=1, dual=0; paths=1; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 335: kind=PRODUCT, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=-1, dual=0; paths=1; roots=[CARRIER +1, CARRIER -1, RECURRENCE]
- 336: kind=PRODUCT, dim=4, recurrence_order=0, factor=2pi, symmetry=S+a, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=13; roots=[CARRIER +1, CARRIER -1, RECURRENCE, SYMMETRY, BOUNDCOND D, BOUNDCOND N]
- 337: kind=PRODUCT, dim=4, recurrence_order=0, factor=2pi, symmetry=S-a, sq=null, anti=null, multiplicity=2, boundary_condition=null, occupancy=null, dual=0; paths=13; roots=[CARRIER +1, CARRIER -1, RECURRENCE, SYMMETRY, BOUNDCOND D, BOUNDCOND N]
- 343: kind=WEIGHT, dim=4, recurrence_order=0, factor=2pi, symmetry=null, sq=null, anti=null, multiplicity=1, boundary_condition=null, occupancy=null, dual=0; paths=1; roots=[CARRIER +1, CARRIER -1, RECURRENCE]

### Distance-2 edge layer

- edge 8094: 331 -> 330; operator=snapshot_v6:0494; paths=1
- edge 8095: 331 -> 313; operator=snapshot_v6:0495; paths=1
- edge 8096: 331 -> 343; operator=snapshot_v6:0496; paths=1
- edge 8097: 331 -> 332; operator=snapshot_v6:0497; paths=1
- edge 8634: 331 -> 336; operator=snapshot_v6:1177; paths=1
- edge 8636: 331 -> 337; operator=snapshot_v6:1179; paths=1
- edge 8638: 331 -> 334; operator=snapshot_v6:1181; paths=1
- edge 8640: 331 -> 335; operator=snapshot_v6:1183; paths=1
- edge 8642: 331 -> 329; operator=snapshot_v6:1185; paths=14

## Stored relation to Node 257

- edge 7779: 257 -> 316; operator=snapshot_v6:0089; paths=210

Classification: STORED_DIRECT_PARENT_RELATION_ONLY.

## Stored relation to Node 331

- edge 8109: 316 -> 331; operator=snapshot_v6:0513; paths=70

Classification: STORED_DIRECT_CHILD_RELATION_ONLY.

## Provenance limit

All edge operators are reported exactly as stored. No missing operator semantics are reconstructed.
