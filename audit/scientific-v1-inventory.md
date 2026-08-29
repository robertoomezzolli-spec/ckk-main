# CKK Scientific v1 · Pre-implementation inventory

Audited at: 2026-08-27 18:45 Europe/Berlin  
Starting main SHA: `c1a8be5a454bf4b4532217616a5daba04cd6b225`  
Sprint package SHA-256: `c389fec843c7d3096f6f039264901bae9564b1edc505b1c21e1456baa6b5ea7c`

All 16 payload files declared by `MANIFEST.json` match their declared byte lengths and SHA-256 hashes.

## Architecture mapping

| Sprint requirement | Status before implementation | Evidence / required work |
| --- | --- | --- |
| Wayback branch + tag | ALREADY_EXISTS | Canonical wayback is `backup/pre-scientific-v1-20260827-184521` and `pre-scientific-v1-20260827-184521` at current main. |
| Neon restore point | ALREADY_EXISTS | Read-only branch `br-little-feather-aw31y5fw`, parent LSN `0/3861078`, independently reproduces Run 34. |
| Sealed historical Run 34 | ALREADY_EXISTS | `v6-noselfdual-563f50e328c5`, run 34, 276 nodes, 945 edges, 196 historical graph convergences, integrity clean. |
| `structural_sig()` | ALREADY_EXISTS | Python `Struct.structural_sig()` excludes derivation provenance. |
| Alternative Derivation Events | NEEDS_EXTENSION | Python expansion retains alternative events and normalizes commutative product identity, but events lack IDs, operator versions, parameters and structural hashes. No database store exists. |
| True derivational confluence | ALREADY_EXISTS | Python helper uses at least two distinct event identities. It is not persisted or exposed through a scientific API. |
| Structure / Derivation / Interpretation separation | NEEDS_EXTENSION | Structure/derivation are partly separated in Python. The legacy database mixes catalog verdicts into structures and has no independent Interpretation entity. |
| Dual roundtrip | ALREADY_EXISTS | Python tests verify `D(D(X)).sig() == X.sig()`. Self-duality remains `NOT_EVALUATED`. |
| Domain-neutral adjudication | NEEDS_EXTENSION | The legacy research prompt is domain-neutral, but one OpenAI worker directly mutates `structures.verdict`; no isolated normalization or restricted judge exists. |
| Fiber order compatibility | MISSING | Current audited core still permits cross-order fiber composition. Existing regression records 1,836 such events. Scientific validation must fail closed when present. |
| Product dual-factor preservation | MISSING | Current audited core still promotes mixed dual products through `max(dual)`. Existing regression records 336 such events. Scientific validation must fail closed when present. |
| Scientific schema + migrations | MISSING | Only legacy `runs/structures/edges/evidence/...` tables exist. |
| Candidate, evidence, normalization, adjudication stores | MISSING | Legacy queue/evidence tables do not satisfy the agent contracts. |
| Frozen versioned canons and targets | NEEDS_EXTENSION | Cross-domain inventory and hashes exist; all four regression canons remain incomplete and cannot be promoted. No immutable CanonTarget store exists. |
| Scientific generation lifecycle | MISSING | No `DRAFT → GENERATED → AUDITED → VALIDATED → SEALED` lifecycle or immutable seal exists. |
| Grammar pressure | MISSING | Legacy proposals are untyped and not enforced as human-review-only. |
| Public SEALED-only projection | MISSING | Public endpoints read sealed Run 34, but no generic scientific-generation public gate exists. |
| Scientific APIs | MISSING | `/api/science/*` does not exist. |
| Dedicated `/science` control plane | MISSING | The Universe has an advanced display toggle only; it is not a scientific control plane. |
| Autonomous worker | MISSING | The legacy worker is a single OpenAI researcher with no scout/red-team/independent-normalizer/judge isolation, budget or circuit breaker. |
| Cross-domain explorer | NEEDS_EXTENSION | Universe renders honest missing-data galaxies. No sealed cross-domain scientific query/store exists. |
| Preview-only delivery | ALREADY_EXISTS | Netlify supports non-production deploy previews; production deploy remains separate. |

## Scientific constraints carried into implementation

- Run 34 is never migrated, rewritten or reclassified.
- The Scientific schema is additive and uses separate `science_*` tables.
- Current core leaks are validation inputs, never hidden by UI or status fields.
- A scoped preview generation may seal only if the operations actually executed in that scope pass all integrity gates; it is not public-eligible while the canons are incomplete.
- Agent output cannot mutate grammar, structures or public data directly.
- `STRUCTURAL_MATCH` is the strongest automatic cross-domain statement.
- `D(X) ≡ X` remains `NOT_EVALUATED`; `MAXDIM=4` remains an experiment parameter.

