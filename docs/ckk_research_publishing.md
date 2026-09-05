# KAIROS CKK research publishing

Production KAIROS exposes a sealed `research.publish(run_id)` model tool. The
tool accepts only the identifier of a completed run created by the networkless
CKK runner. It cannot accept HTML, Markdown, claims, destinations, filesystem
paths, or arbitrary content.

The knowledge adapter validates the run request/result pair, repository, exact
commit SHA, seed hash, source paths, controls, compute limits, operator names,
and provenance before creating an immutable publication. A second publication
of the same run is idempotent; a changed source digest is rejected.

Publications are stored in the separate `ckk-research-publications` Docker
volume. The canonical `robertoomezzolli-spec/ckk` mirror remains fetch-only and
is mounted read-only in the network-sealed runner. The read-only site serves:

- `/research/`
- `/research/<run-id>`
- allowlisted JSON/Markdown/raw run downloads below that run URL

The renderer separates SOURCE, RUN, INTERPRETATION, HYPOTHESIS, and VERDICT.
It publishes no WhatsApp records and rejects artifact fields whose names imply
credentials, phone data, authorization, or private messages. Generated run
evidence remains `belief_status=not_committed`; normal NREM/REM/hysteresis is
the only route to later persistent belief.
