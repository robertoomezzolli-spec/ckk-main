# CKK Scientific v1 · Test report

Final local run: 2026-08-27 Europe/Berlin

| Gate | Result |
| --- | --- |
| Node unit/API/integration tests | `52 PASS / 0 FAIL` |
| Python generator/regression tests | `22 PASS / 0 FAIL` |
| Playwright browser tests | `8 PASS / 0 FAIL` |
| Vite production build | `PASS` |
| Production dependency audit | `0 vulnerabilities` |

Scientific-specific coverage includes:

- provenance-complete controlled generation;
- deterministic structure and DerivationEvent hashes/IDs;
- true confluence semantics independent of binary arity;
- deeper current-core cross-order rejection;
- normalizer input isolation;
- third-normalization prohibition;
- interpretation/label leakage rejection;
- additive migration and immutable triggers;
- write-auth and preview-only seal API rules;
- SEALED-only public API projection;
- five-call Discover→Seal contract replay;
- all `/science` views, generation inspector and structure inspector;
- honest empty states for disputes and cross-domain matches.

Browser screenshots:

- `screenshots/science-01-overview.png`
- `screenshots/science-02-candidate-queue.png`
- `screenshots/science-03-disputes.png`
- `screenshots/science-04-failures.png`
- `screenshots/science-05-grammar-pressure.png`
- `screenshots/science-06-generation-inspector.png`
- `screenshots/science-07-cross-domain.png`
- `screenshots/science-08-structure-inspector.png`

The contract replay uses explicit test doubles and is not reported as a real GPT/Claude scientific run. The real external cycle remains separately gated by explicit outbound approval.

