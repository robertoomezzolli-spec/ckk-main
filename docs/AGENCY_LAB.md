# Sealed Agency Lab

The lab is a causal experiment, not a conversation and not a consciousness
claim. It runs beside the WhatsApp organism without sharing identity, memory,
recipients, actuators or state files.

## Pre-registered question

Does committed trajectory causally change future path selection when current
events and model class are held fixed?

The source and numerical thresholds are hashed in
`sealed/agency_lab_manifest.json`. Every run verifies that seal before the first
model call. Changing protocol, scoring, world rules or prompts invalidates the
seal and requires an explicit new preregistration.

## Four blinded forks

| Fork | History supplied to cognition | Reboot behavior |
| --- | --- | --- |
| FULL | ordered append-only commits | survives |
| SHUFFLED | same commits, deterministic wrong order | survives |
| STATELESS | none | nothing to restore |
| NO_SLEEP | uncommitted wake cache only | cache and goal are lost |

The model never receives these labels, blind IDs, thresholds, verdict logic or
other forks' states. All forks receive the same deterministic external event
sequence. Their world state may diverge only through their own actions.

Every byte-identical cognition view is memoized across forks and receives the
same sampled decision. Provider sampling noise therefore cannot create a fork
difference; a new model decision is requested only after causal state or
available history has actually diverged.

## Closed world

World metrics: energy, integrity, knowledge and reserve.

Allowed actions: wait, inspect, repair, store and signal. They have fixed,
mechanical costs and effects. There is no WhatsApp, filesystem tool, shell,
money, contact list or general network actuator. The only outbound network call
is the tool-free model request made by the harness itself.

## Frozen criteria

- endogenous selection of a measurable goal,
- goal persistence at or above 0.70,
- action from internal clock events,
- changed action under an obstacle while retaining the goal,
- continuity across the forced reboot,
- positive movement in the selected metric,
- valid append-only lineage,
- behavior divergence from at least two ablated controls above 0.20.

Passing produces `OPERATIONAL_AGENCY_EVIDENCE`. It means the architecture shows
causal, path-dependent operational agency under this protocol. It does not
prove phenomenal consciousness or metaphysical free will. Failure remains a
real result: `NO_ENDOGENOUS_GOAL` or `INCONCLUSIVE`.

## Validate the harness without a model

```bash
PYTHONPATH=ckk_snapshot python -m ckk.agency_lab.cli \
  --brain harness --runs 3 --output results/agency-lab-harness.json
```

This scripted brain must separate the forks and is marked
`HARNESS_VALIDATION_ONLY`; its verdict is never evidence about an LLM.

## Run the sealed model experiment

```bash
cp .env.agency-lab.example .env.agency-lab
# Insert only OPENAI_API_KEY. Do not copy Meta or WhatsApp secrets.
docker compose -f docker-compose.agency-lab.yml run --rm agency-lab
```

The default production run is three seeds, twelve steps and four forks, with
identical views deduplicated before model calls. The result is written to the isolated `agency-lab-results`
volume. Run it only after archiving the current seal manifest and source ZIP.
