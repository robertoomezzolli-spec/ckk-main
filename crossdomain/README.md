# CKK Cross-Domain Golden Suite

This directory is a fail-closed scientific inventory. It distinguishes exact executable fixtures from partial historical research records and never reconstructs missing seeds from narrative descriptions.

| Domain | Archive status | Executable seed | Frozen output | Regression status |
| --- | --- | --- | --- | --- |
| Physics | `FOUND_EXACT` | yes | no | blocked |
| Chemistry | `FOUND_PARTIAL` | no | no | blocked |
| Biology | `FOUND_PARTIAL` | no | no | blocked |
| Computation | `FOUND_PARTIAL` | no | no | blocked |

The Physics seed fixture is the exact built-in seed set of the current audited core. It is not a complete golden regression because its reviewed structural-output set and independent hold-outs were never frozen.

For Chemistry, Biology, and Computation, sealed historical methodology documents were recovered from `CKK_testsuite.zip`. They record domain-neutral missing distinctions, but do not contain executable seed lists, frozen output sets, or hold-out catalogs. Those documents are preserved byte-for-byte under each domain's `provenance/` directory. They are evidence of prior work, not substitutes for fixtures.

Every domain directory contains the same four machine-readable records:

- `seed.fixture.json`
- `expected.structural.json`
- `holdouts.json`
- `metadata.json`

Unavailable data is represented by `null` and a blocking reason. `SHA256SUMS.json` seals all suite inputs. Any scientific completion must arrive as a new reviewed artifact; existing records must not be edited to fit a later result.

Run `python3 scripts/crossdomain-golden-gate.py`. Exit code 0 is reserved for a fully frozen four-domain suite. `--allow-incomplete` is inventory-only and cannot certify a regression pass.
