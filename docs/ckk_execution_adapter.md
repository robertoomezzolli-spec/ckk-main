# Sealed CKK execution adapter

Production KAIROS receives two Responses API tool namespaces: `whatsapp` and
`ckk`. The resulting logical capability registry is `whatsapp.send`,
`ckk.search`, `ckk.read`, `ckk.symbol`, and `ckk.run`.

`ckk.search`, `ckk.read`, and `ckk.symbol` are served by the internal knowledge
adapter from a fetch-only Git mirror of
`https://github.com/robertoomezzolli-spec/ckk`. Every access resolves a full
commit SHA. Repository paths are Git-tree paths, not arbitrary host paths.

`ckk.run` writes a validated job to a private Docker volume. The `ckk-runner`
service consumes it with `network_mode: none`, a read-only mount of the Git
mirror, a read-only container root, dropped capabilities, `no-new-privileges`,
and explicit wall-time, address-space, file-size, process, state, and
derivation limits. It extracts only the pinned repository's `grammar.py` and
`expand.py` and invokes `expand_auditable` or
`expand_structural_auditable`. Full generated provenance is stored on the
`ckk-run-artifacts` volume; only a bounded projection enters model context.

CKK content is labeled external and unverified. Tool results are ephemeral and
are not valid learning evidence in the current WAKE. The persistent tool audit
stores hashes and provenance only, never retrieved excerpts or arguments. This
keeps belief promotion behind the existing NREM/REM/hysteresis boundary.

No shell, Git write, arbitrary filesystem, or network operation is exposed to
the model. `whatsapp.send` in the model registry is a deferred proposal; the
existing runtime capability policy and actuator remain authoritative for any
real outbound message.
