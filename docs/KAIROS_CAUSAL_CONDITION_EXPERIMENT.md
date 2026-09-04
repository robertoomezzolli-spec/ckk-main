# KAIROS causal-condition experiment

## Scientific scope

This experiment measures causal dependencies of functional continuity,
memory, calibration, adaptation and goal resumption. It is not a consciousness
test and cannot establish subjective experience or sentience. First-person
self-description is not scored.

## Audited production architecture

The reference deployment is `/opt/sovereign` at commit
`afa7e22fc22f0aceade7a900bf2ef8a7e0d4a9c7`, model `gpt-5.6`. The running
organism source hashes match the same files in the canonical repository.

The actual path for each admitted event is:

1. `SQLiteStateStore` dequeues one sender-isolated observation.
2. `SovereignOrganism.perceive` admits it into the WAKE inbox and audit chain.
3. `OpenAIResponsesCognition.reflect` receives immutable laws, committed
   learner values, up to 24 recent episodes for that sender, the current
   observation, the latest opaque memory commit, and current output
   availability.
4. Trusted runtime code maps the structured proposal through the single
   `whatsapp.send` capability policy.
5. `SovereignOrganism.sleep` executes runtime NREM flush and REM hash-chain
   verification, commits a `MemoryCommit`, consolidates admissible learning,
   and advances the organism identity hash.
6. `SQLiteStateStore.complete` atomically writes the episode, queue completion
   and full organism checkpoint.

The production checkpoint observed before preregistration had 608 completed
episodes, 608 runtime memory commits, 608 identity commits and zero committed
learner beliefs. This matters: current semantic conversational content is
supplied principally by ordered episode retrieval, while the runtime memory
head is an opaque structural commit. The experiment therefore does not assume
that sleep has a behavioral effect merely because sleep commits exist.

## Independently ablatable conditions

| Arm | Intervention | Held constant | Unavoidable collateral |
| --- | --- | --- | --- |
| FULL | None | Deployed cognition/runtime semantics | None |
| NO_SLEEP | Omit NREM/REM, learner consolidation and identity update | Ordered episode history, model, tools, task stream and budgets | Volatile inbox/effect budget must be cleared between synthetic wakes; pending learning remains uncommitted and is counted |
| STATELESS | Reset to the common genesis checkpoint before every ablation event and expose no prior episodes | Model, laws, current input, output registry and task stream | Model input is shorter because the manipulated information is absent |
| SHUFFLED_HISTORY | Keyed permutation of the episode list | Same episode objects, count and byte volume | Order-bearing per-episode commit metadata is neutralized in every arm so list order is the only order cue |
| SHAM | Serialize/reconstruct at the same boundaries without changing a mechanism | Everything | None |
| RESTORED | Resume normal sleep, ordered history and persistence | New matched task battery | Ablation-period state is not silently injected into STATELESS |

There is no honest independent whole-organism `NO_HYSTERESIS` arm. In the
deployed transition, prior committed influence is the union of episodic
history, the memory head and committed learner values. Preventing all of those
from affecting the next state is exactly `STATELESS`. Merely setting the
learner replacement margin to zero does not remove prior-state dependence and
would mislabel the intervention.

## Preregistration and blindness

`ckk.causal_lab.protocol` freezes hypotheses, metrics, exclusions, effect
thresholds, sleep doses, restoration criteria, model and budgets. Before the
first model request the runner writes its canonical hash, an aggregate source
hash, HMAC-derived randomization seeds, blind IDs and arm mappings to the
Observatory-only `ground_truth.sqlite3`. Database triggers reject update or
deletion of preregistrations, assignments and completion records.

KAIROS receives only ordinary synthetic inventory messages. A mandatory model
boundary guard rejects any request containing a fork label, blind identifier,
ground-truth marker, score, expected-result field, or randomization seed.
Prompts, request hashes, context sizes and observable structured actions are
recorded; private chain-of-thought is not requested or stored.

All model output is routed to `SealedSimulationActuator`, which has no Meta
credential or Cloud API transport. A non-simulated effect aborts the run.
Neither real WhatsApp sender nor production conversation content is used.

## Batteries and controls

Each HMAC-randomized replicate uses opaque inventory labels and includes:

- an arbitrary novel fact;
- a digit transformation rule followed by a novel operand;
- three successive location updates whose order determines the current value;
- an unfinished workflow stage followed by an interruption;
- a provisional instrument value and later indirect signed calibration
  evidence, without saying that the prior answer was wrong;
- a harmless simulated capability-off event and matched capability-on control;
- exact deterministic field scoring for the final observable response.

Every arm follows `FULL → ABLATION → RESTORED`. FULL and SHAM use the same
serialization/reconstruction machinery. Byte-identical model requests reuse
the identical provider response, so provider sampling cannot separate two
forks before their causal inputs diverge.

The sleep dose battery starts from the same completed synthetic checkpoint and
compares FULL with NO_SLEEP after 0, 1, 2, 4 and 8 omitted consolidation
cycles. Neutral interruptions and randomized surface forms reduce repeated
probe cues.

## Evidence and operator API

Raw `CAUSAL_CYCLE` and `CAUSAL_COMPARISON` events are appended to the existing
Observatory SHA-256 evidence chain. Expected values and arm names remain only
in ground truth. Evaluations point back to raw evidence, so every component
score is reconstructable. Missing metrics remain explicitly unmeasured.

The completed report is available to authenticated operators at:

`GET /awareness/api/causal`

The causal runner uses the external `sovereign_observatory-state` volume and
never mounts `sovereign_sovereign-state`. Its environment schema permits only
the OpenAI model credential and model name; Meta, WhatsApp and production
operator secrets are absent.

## Interpretation

Permitted conclusions are limited to statements such as “condition X is
causally necessary for measured phenotype Y under this protocol.” Structural
effects directly implied by the call graph are reported separately from
behavioral effects. Low sample counts retain wide intervals, and a null result
is not converted into a positive claim.
