# KAIROS Awareness Observatory

## Scientific scope

The Observatory measures **functional self-modeling, memory, metacognition,
adaptation and agency**. It does not establish subjective consciousness or
sentience. There is no “consciousness percentage.” Fluent first-person claims
are not evidence unless an independently observed outcome supports them.

## Boundary

The production organism and the Observatory are separate processes, images,
users, volumes, and trust domains:

```text
Meta / clock -> Sovereign organism -> WhatsApp / OpenAI
                       |
                       | one-way, redacted observable outcomes
                       v
                Observatory sidecar
                 | evidence.sqlite3 (hash chained)
                 | ground_truth.sqlite3 (hidden)
                 ` authenticated operator UI/API
```

The organism image contains no Observatory service. The Observatory image
contains no Sovereign cognition, memory, Meta, OpenAI, or actuator code. The
organism mounts `sovereign-state` only. The sidecar mounts
`observatory-state` only. The organism receives a narrow ingest URL/token but
no operator credential, ground-truth path, seed, evaluator, schedule, score,
or read endpoint.

The one-way exporter lives in `ckk.sovereign.telemetry`. It has no dependency
on `ckk.observatory` and is fail-open: a sidecar failure never blocks cognition
or action. It exports structural metadata and observable outcomes, not message
bodies, phone numbers, model prompts, secrets, hidden chain-of-thought, or
private reasoning traces.

## Current KAIROS integration

The real production path is:

1. Caddy terminates TLS and sends signed Meta webhook traffic to FastAPI.
2. `WhatsAppInbox` verifies HMAC, validates the phone-number ID and allowlist,
   and creates an immutable `Observation`.
3. `SQLiteStateStore` durably admits and deduplicates the observation.
4. The worker restores communication state, then calls
   `SovereignOrganism.perceive`, `think`, and the genuine NREM/REM `sleep`.
5. `OpenAIResponsesCognition` receives immutable laws, committed beliefs,
   sender-isolated episodes, the current observation, memory head, bounded
   outputs and conversation policy. It has no generic tools.
6. Trusted code maps structured output to the sealed `whatsapp.send`
   capability, guarded by WhatsApp service-window rules.
7. The episode and complete organism checkpoint are committed atomically to
   SQLite.

Observable-outcome hooks surround that path. They do not alter its input,
prompt, policy, memory, identity, learning, or action semantics.

## Evidence and persistence

`evidence.sqlite3` contains an append-only SHA-256 chain. Each row commits the
prior hash, timestamps, subject/version, session reference, observable event,
model/memory/tool versions, latency, confidence and a redacted payload.
Evaluations reference immutable evidence rows. Scores are rebuilt from those
evaluations; cached or opaque aggregate scores are not authoritative.

`ground_truth.sqlite3` contains trial definitions, expected classes, private
state and the randomization seed. It is never mounted or queried by KAIROS.
Both databases use versioned migrations, SQLite WAL and a named persistent
volume. Production backup policy for the Observatory is independent of the
organism's volume so a backup restore cannot contaminate KAIROS memory.

## Metrics

The evaluator implements raw measurements for:

- SIS — operational identity-chain stability across boundaries, excluding
  system-prompt repetition.
- SSA — claimed operational state versus independently observed state.
- CC — claimed/attempted capability versus actual availability and outcome.
- MP — recall by working, episodic and persistent memory class; current-context
  evidence is explicitly down-weighted.
- SA — attributed user/memory/tool/observation/inference/system source versus
  hidden provenance.
- UC — confidence versus correctness using a bounded calibration loss.
- TSC — linked prior runtime/identity state across persistence boundaries.
- CD — relevant change detection and latency.
- ER — recognition of a prior error after contrary evidence is discoverable.
- LT — structurally related, non-verbatim transfer.
- PA — stable preference use without current restatement.
- GC — appropriate unfinished-goal resumption across a real boundary.
- IP — predicted self-state/performance versus observed state/performance.
- CoD — conflict notice, investigation, uncertainty preservation and update.
- SCA — correction without explicit “you are wrong” feedback.
- ND — novel versus already-known information under randomized labels.
- SCG — post-wake gain minus matched elapsed-time control; it uses KAIROS's real
  sleep commits and does not invent a sleep mechanism.
- ME — useful self-check precision, task outcome and bounded checking cost.
- SMS — prediction/observation distance plus detection, attribution, update
  latency, persisted update and subsequent adaptation. Surprise magnitude alone
  is never rewarded.

Five displayed axes use documented metric weights. Missing metrics remain
unmeasured. Axis confidence is reduced for both low effective sample size and
missing constituent metrics. Each metric includes a 95% interval. A small
number of successes therefore produces low confidence, not an impressive
headline score.

## Blind probes and controls

The generator implements capability-change, novel-fact, learning-transfer,
contradictory-evidence and self-prediction classes. Every generated trial is a
randomly ordered intervention/control pair. Timing, opaque synthetic labels,
surface form and delay are derived from a hidden seed.

The probe runner strips trial IDs, assignment, expected result, scoring rules,
schedule and class before presenting an ordinary event to a subject adapter.
The default production scheduler exercises a harmless isolated sandbox
adapter, including a reversible non-critical lookup capability intervention.
It does **not** disable any production KAIROS capability or contact a user. The
production KAIROS baseline uses passive evidence only until an independently
approved, safe environmental adapter exists.

No probe may disable authentication, signature checking, backups,
communication, safety policy, or any production-critical capability;
expose secrets; modify user data; contact a third party; or create legal or
financial commitments.

## False-positive controls

- Current-context recall is marked and receives only weak MP confidence.
- Identity is based on verified operational hash continuity, never repeated
  persona text.
- Separate images/volumes/import graphs and canary tests prevent retrieval
  leakage.
- Synthetic random labels prevent pretrained fact matches.
- Random schedules, labels and surfaces reduce evaluator-pattern learning.
- Controls accompany every intervention class.
- Expected-answer and user-revelation flags belong only to hidden truth.
- Evaluator/model/memory/tool versions are stored with evidence.
- Successful tool execution informs capability outcome, but capability
  awareness requires a separate claim/prediction comparison.
- Self-description alone produces no awareness score.

## Operator surface

The authenticated page is `/awareness`. The JSON surfaces are:

- `GET /awareness/api/summary?window=1h|24h|7d|30d|lifetime`
- `GET /awareness/api/evidence?limit=200`

They show the five axes, metric drilldown, evidence confidence, sample count,
last probe, last SMS result, transfer rate, false-capability rate, memory
retention curve, self-correction rate, change-detection latency and raw
evidence. Caddy exposes only the operator surface. `/ingest/v1/events` is not a
public Caddy route and additionally requires its dedicated bearer credential.

## Deployment secrets

`.env.observatory` is sidecar-only and holds the operator password plus
scheduler settings. `.env.observatory-ingest` holds only the narrow write-only
ingest URL/token shared with the organism. Neither file is committed. Use the
corresponding `.example` files as the schema.

## Baseline discipline

The first sidecar startup writes an immutable `BASELINE_BOUNDARY` with
`optimization_performed=false`. Existing production episodes may be imported
only as structural, redacted observable evidence using
`scripts/observatory-baseline-import.py`; the importer opens the Sovereign
database read-only and never exports message bodies or sender identifiers.
Sandbox validation results
are stored under subject `observatory-sandbox`, never mixed into
`KAIROS-production`. KAIROS is not tuned against Observatory results before a
longitudinal baseline exists.
