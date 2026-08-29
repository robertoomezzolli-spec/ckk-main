# CKK Cross-Domain Universe Web App

## Data contract

- Display source: sealed Run 34 export
- Generation: `v6-noselfdual-563f50e328c5`
- Source SHA-256: `8627e79c0b7ef61a2d989290c2250003f837590d37cb2c99fa9c31d008335a90`
- Nodes: 276
- Edges: 945
- Historical graph confluences: 196
- True derivational confluences from this snapshot: `NOT_VERIFIABLE_FROM_SNAPSHOT`
- Self-duality: `NOT_EVALUATED`
- `MAXDIM=4`: experiment parameter, not a spacetime-discovery claim

The client validates generation, run, counts, duplicate IDs, dangling edges, self-loops, dual=2 assertions, and stored integrity before showing the app.

## Domain display

- Physics: 276 Run 34 structures, `FOUND_EXACT`
- Chemistry: zero generated structures, `FOUND_PARTIAL`, visible missing-data galaxy
- Biology: zero generated structures, `FOUND_PARTIAL`, visible missing-data galaxy
- Computation: zero generated structures, `FOUND_PARTIAL`, visible missing-data galaxy
- Certified cross-domain bridges: zero

Missing-data galaxies are spatial status markers. They contain no synthetic scientific nodes or matches.

## Implementation

- Vite production build
- locally bundled Three.js; no runtime CDN
- WebGL2 with `THREE.InstancedMesh` for structures
- buffered relation lanes and point-cloud nebulae
- inertial orbit/flight controls, camera transitions, status filters, guided tour
- generated structure and catalog annotation are separate in every node card
- WebGL fallback and fatal snapshot-validation state

## Browser validation

Chrome/SwiftShader WebGL was used for the reproducible smoke suite. The tests cover application load, Run 34 validation, all domain states, filters, guided tour, cross-domain bridge state, node cards, scientific mode, WebGL canvas output, and absence of fatal console errors.

Screenshots:

1. `screenshots/01-universe-overview.png`
2. `screenshots/02-physics-galaxy.png`
3. `screenshots/03-chemistry-galaxy.png`
4. `screenshots/04-biology-galaxy.png`
5. `screenshots/05-computation-galaxy.png`
6. `screenshots/06-cross-domain-bridge.png`
7. `screenshots/07-rediscovered-node.png`
8. `screenshots/08-unmatched-node.png`
9. `screenshots/09-physics-card.png`

## Known limitations

- Chemistry, Biology, and Computation cannot show generated stars until exact executable fixtures and reviewed outputs are recovered.
- Run 34 stores `snapshot_v6:*` edge identifiers, so named operator provenance must not be reconstructed in this view.
- The current Python core fails the cross-order fiber and mixed-dual product regression gates; no new generation was created.
- The bundled Three.js entry is about 590 kB minified (about 150 kB gzip) and triggers Vite's 500 kB chunk warning.
- The measured SwiftShader performance is a smoke floor, not a hardware benchmark.
