# Frozen CKK experiment supervisor

This is operational tooling around production KAIROS. It does not alter the
organism's cognition, identity, memory, learning, hysteresis, sleep lifecycle,
or WhatsApp actuator.

## Fixed scientific target

- repository: `https://github.com/robertoomezzolli-spec/ckk-main`
- branch: `experiment/solar-system-provenance-cascade`
- commit: `5faf926d6cc324e08c32649e1b92cf57f3c56cb3`
- experiment: `fresh-seed-closure-plateau-v2`
- entrypoint: `experiments/fresh_seed_closure_plateau_gate_v2_run.py`

`sealed/fresh_seed_closure_plateau_v2_execution_manifest.json` contains every
committed preregistration threshold, the exact-floor null, source hashes and
the freeze statement. `repo.read(operation="manifest", ...)` recomputes every
source hash against the pinned Git tree. The caller must pass the returned
manifest SHA-256 into every `process.run` request.

## Capability surface

- `repo.read`: sync the single fixed mirror, select a commit, inspect status,
  inspect a bounded diff, read a Git-tree path, or verify the manifest.
- `process.run`: start only `supervisor_smoke`, `equivalence_validation`, or
  `fresh_seed_closure_plateau_v2`. Starts are idempotent for a matching task,
  commit, manifest and compute profile; an explicit `retry_of` is required to
  repeat a matching failed execution.
- `process.status`: inspect queued/running/terminal state, PID, runtime,
  resources, exit code, termination class and artifact hashes.
- `process.stop`: request TERM, then KILL after a grace period, for a sealed
  experiment job only.
- `file.read`: bounded text reads under the experiment artifact volume only.
- `file.hash`: streaming SHA-256 under that artifact volume only.
- `system.metrics`: read worker CPU/memory/cgroup/OOM and artifact-disk state.

There is no command string, repository URL, destination path, shell, package
installer, push operation, general network operation, arbitrary filesystem
path, or root privilege in the tool schemas.

## Supervisor

`ckk-experiment-worker` is the persistent job supervisor. It is independent of
an interaction and has no network. It receives an allowlisted request through
a private volume, extracts exactly one Git commit from a read-only mirror,
verifies every source hash, makes source read-only, and launches one fixed
Python entrypoint. Jobs and logs survive organism restarts. A supervisor
restart marks an in-flight process `INTERRUPTED`; it never fabricates a
scientific result. A job started from an admitted WhatsApp service window is
bound privately to that conversation. Its terminal state is later delivered
to KAIROS as an ordinary sealed-supervisor observation, allowing a new WAKE to
report the outcome instead of busy-polling inside one model response. This is
not Observatory feedback and contains no Observatory ground truth.

The container has all Linux capabilities dropped, `no-new-privileges`, a
1,152 MiB resident-memory cgroup ceiling, swap-backed 5 GiB combined memory
ceiling, 0.80 CPU quota and 64-PID ceiling. The production host provisions a
dedicated 4 GiB swap file so the frozen graph build can exceed 1 GiB without
endangering the organism. Per-task RLIMITs
are returned as `operational_compute_limits`. Timeout, address-space limit,
cgroup OOM kill, manual stop, equivalence failure, ordinary non-zero exit and
normal completion have distinct terminal classifications. These are compute
outcomes, not scientific outcomes.

Python 3.12 is fixed by the image. The committed experiment imports only the
Python standard library. Every job persists `environment.json`, source hash
verification, manifest and manifest hash, request, execution metadata,
stdout, stderr, final status and result/equivalence artifact.

## Mandatory order

All arguments are structured tool arguments, not shell commands:

1. `repo.read` with `operation="sync"`.
2. `repo.read` with `operation="checkout"` and the full frozen commit.
3. `repo.read` with `operation="manifest"`; retain `manifest_sha256`.
4. `process.run` with `task="equivalence_validation"` and that hash.
5. Poll `process.status`; optionally use `system.metrics`.
6. Continue only if state is `COMPLETED` and `equivalence_passed=true`.
7. `process.run` with `task="fresh_seed_closure_plateau_v2"`, `retry_of=null`,
   and the same hash. Return the queued job ID immediately; completion arrives
   as a later supervisor observation.
8. Poll `process.status`; read the returned `result_path` with `file.read` and
   independently hash it with `file.hash`.

The server rejects step 7 until a matching, completed equivalence proof exists.
Scientific result interpretation is not part of this tooling and is never
written directly into KAIROS beliefs.

## One-way observability

Model capability calls are hashed in the organism's tool audit. Sanitized
experiment invocation and job-state transitions are also emitted to the
external Observatory as `CAPABILITY_INVOKED` and `EXPERIMENT_JOB_STATE`.
Only operation/task, timestamps, status, exit state and artifact provenance
are exported. Artifact contents and model/user text are not exported, and no
Observatory data is mounted or returned to cognition.
