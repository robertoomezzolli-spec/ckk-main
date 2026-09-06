# Scientific derivation integrity v2

Review date: 2026-09-06. Base: `4825d7ec52e95f1059069e5e7ac4848ae94757d8`.

The scientific export counted repeated scheduler observations as independent
derivations, disagreed with JavaScript on commutative input hashing, and could
validate well-hashed but impossible operator applications. This change fixes
those three problems without changing the Python grammar, seeds or operators.

## Event identity

`ckk-derivation-v2` identifies an application by operator/version, ordered input
ID/hash pairs, output ID/hash and operator parameters. Only `op_product` sorts
its complete input pairs. Observation `level` is metadata and is excluded from
the identity. The exporter retains the first observed level when an application
recurs. Confluence counting recomputes canonical identities instead of trusting
caller-supplied or historical event hashes.

Python and JavaScript both hash the versioned canonical JSON envelope. The
generation exporter derives its operator version from the loaded grammar's
SHA-256 and rejects a contradictory `--operator-version` argument.

## Structural replay

`science/replay.mjs` independently implements the structural effects and
admissibility predicates of the pinned Python grammar for validation only.
Its supported source hash is:

`afd52bc69b014d418826c400d2eb5e159ca41fb3e60fee68f8da90dcf18e89da`

Every application must name a registered operator and supported version, supply
the right number of inputs and exact supported parameters, meet the operator's
preconditions, and reproduce the stored structural output. Every hash must
remain attached to the corresponding input. Admitted seeds must belong to the
pinned canonical seed table. The verifier reconstructs canonical symmetry seed
labels from that table; it does not use interpretive names as structural facts.

Validation also checks that all inputs of each replayed application are derived
from admitted seeds at earlier observation levels. A disconnected dual cycle,
or one parent of a binary operation, cannot establish provenance by itself.
This validates an observed derivation graph; it does not certify exhaustive
exploration of the grammar or physical interpretation of its nodes.

The JavaScript verifier deliberately rejects unreviewed grammar hashes and
operator versions. If the Python source changes, review the verifier and its
differential regression tests before enabling that grammar. The verifier is
not a second candidate generator and does not feed anything back into CKK.

## Compatibility and rollout

`science-validator-v2.0.0` and `ckk-derivation-v2` apply to fresh scientific
exports. Their event hashes/IDs differ from v1. Preview generations use a
`sci-v2-preview-` identity that includes the event identity version, and record
the version in their scope. The grammar version itself is unchanged.

Historical Run 34, sealed scientific generations, stored v1 event IDs, and
published experiment results are not rewritten or recertified by this change.
Do not feed old event hashes into a v2 certification and interpret the resulting
hash failures as a change to the historical grammar. A comparison requires a
fresh generation and explicit identity-version attribution.

No production migration or deployment was executed for this branch. An existing
separate storage constraint remains: the checked-in scientific schema declares
`maxdim NOT NULL`, while the unbounded Python grammar exports `maxdim=null`.
The database schema must be reconciled before deploying the unbounded export
to that schema. The worker integration test uses an in-memory store and does
not certify database persistence. This patch does not change that schema.

## Verification

Commands run locally against the pinned base plus this patch:

```sh
node --test test/science-core.test.mjs test/science-integrity.test.mjs test/science-worker.test.mjs test/science-api.test.mjs
python3 -m unittest discover -s test -p 'test_generator_core.py' -v
git diff --check
```

Results: 23 JavaScript tests and 15 unchanged Python kernel tests passed.
All eleven registered operators occur in the level-5 differential check.
The entire level-5 export validates with 4,491 replayed applications and no
unreachable generated structures. Invalid applications were tested after
recomputing their hashes and IDs, so rejection cannot rely only on a stale hash.

| Level | Unchanged states | v1 exported events | v2 unique events | v1 confluent states | v2 confluent states |
|---:|---:|---:|---:|---:|---:|
| 2 | 52 | 47 | 42 | 5 | 0 |
| 3 | 204 | 410 | 363 | 150 | 133 |
| 4 | 604 | 1,953 | 1,543 | 462 | 449 |
| 5 | 1,403 | — | 4,491 | — | 1,084 |

The v1 columns are the measurements from the preceding source audit, not
physical golden fixtures. The v2 counts match the unchanged Python
`Derivation.event_key()` semantics. No claim about SRT, new physics, or the
separate experimental plateau is changed by this repair.
