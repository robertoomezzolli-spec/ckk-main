# CKK knowledge adapter

Production KAIROS reads CKK through an internal, read-only evidence adapter. The
source is `https://github.com/robertoomezzolli-spec/ckk` at the configured Git
ref. The adapter maintains a fetch-only Git mirror and an atomic SQLite index in
the `ckk-knowledge-cache` volume. Its push URL is deliberately disabled.
The private repository is authenticated with a repository-specific, read-only
GitHub deploy key mounted as a Docker secret. Strict host-key checking uses a
GitHub-published known-hosts file; no personal GitHub token enters the container.

The adapter offers authenticated internal endpoints for hybrid, exact, symbol,
filename and deterministic local vector search, commit history, and bounded
commit diffs. It is not routed through Caddy. Every result contains repository,
ref, full commit SHA, blob SHA where applicable, path, line span, evidence class,
content digest, retrieval method, and a bounded excerpt.

Only messages that express CKK/source/provenance intent trigger retrieval. At
most six results and 12,000 excerpt characters enter a single WAKE as
`ckk.repository/evidence.source` observations. CKK files, the index, query
schedule, and Git client are not mounted into the organism container.

CKK evidence is labelled `external_evidence_unverified` and `not_committed`.
The normal cognition path may propose a durable belief only by citing a current
evidence observation; the existing admission threshold, NREM flush, REM audit,
and hysteretic consolidation then apply. There is no direct index-to-belief
write. Sovereign persists only compact source provenance for audit/backtrace;
retrieved excerpts are excluded from episodic history and checkpoints.

The real `CKK_ADAPTER_TOKEN` belongs in `.env.ckk-knowledge`, never Git.
