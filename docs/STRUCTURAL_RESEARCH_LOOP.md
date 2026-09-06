# Checkpointed structural research loop

The coordinator in `scripts/structural-research-loop.py` runs a finite sequence
of nested scopes over the existing boundary experimental dialect. It is not a
claim that a system can detect complete coverage of nature.

The loop automatically generates paired control/extension runs, replays all
recorded applications, compares their reachable state sets, samples a complete
seed-rooted backtrace and checkpoints each completed iteration. Kernel sources
and the protocol are hash-pinned. It does not edit operators or seeds, call a
model, consult a catalog or optimize against target answers.

## Run and resume

```bash
python3 scripts/structural-research-loop.py --checkpoint audit/my-loop.json
```

The default schedule uses leaf/depth bounds `(2,2), (3,3), (3,4), (3,5), (4,5)`.
Each arm gets 5,000 nodes, 50,000 events, 16 frontier rounds and 20 seconds of
generation time. Replay/reporting time is additional. The maximum schedule is
20 iterations. There is no background service, scheduler or unlimited process.

Checkpoints are written atomically and carry a content hash. Source or protocol
changes require a new checkpoint filename. An interrupted checkpoint resumes
after reproducing the last completed iteration's graph fingerprints. Completed
schedules and resource stops are returned as terminal records; they are not
silently rerun with higher budgets. A new experiment is required to widen budgets.
The content hash detects accidental corruption, not authenticity against someone
who can rewrite the file and recalculate its hash.

## Interpretation of decisions

| Decision | Meaning |
| --- | --- |
| STRUCTURAL_GROWTH | New generated descriptors appeared in a completed bounded scope. |
| NO_STATE_GROWTH_IN_THIS_SCOPE | Two completed nested scopes have the same state set. This does not establish a global fixed point. |
| COMPUTE_LIMIT_REACHED | A run was truncated. Missing states and absent control containment cannot establish structural regression. |

Loss of a previously reached state between two *saturated*, nested scopes is an
error. A truncated larger run may miss deep states reached by a smaller complete
run because the frontier traversal allocates its finite node budget differently.
The report records those missing states rather than hiding them.

Novelty here is structural set difference. It is not a native DIRECT, UNMATCHED
or discovery verdict. The first iteration's difference is relative to an empty
observation set and includes admitted seeds. Role/depth growth and old scalar
projection classes remain available in each iteration's runner report.

## External scientific gate

The checkpoint records `external_evaluation=NOT_RUN` and
`nature_coverage=NOT_DEFINED`. Executable independent domain fixtures and a
justified interpretation bridge are not configured for this dialect. Four domain
metadata records fetched from commit `645639d8951ef3ad842f890adfc4005daca3412c`
are preserved in `audit/loop-external-readiness-20260906.json`. All are marked
non-certifiable in that archive. Its historical MAXDIM metadata does not replace
the current kernel configuration.

An external test suite must be frozen independently of generated answers, run
after generation and report unsupported cases and counterexamples. It must not
feed interpretations into the kernel. Rule revisions remain separate source
versions with explicit assumptions and regression tests. This coordinator does
not yet automate the design or admission of such revisions.

Winding, weighting/filtering, exclusion/filling and symmetry actions are still
outside the current combined experimental dialect. No production graph, API or
UI was switched to it.
