# Sovereign Runtime: senses without direct power

## Primary target

The primary new module is Path B, the Sovereign Agent Runtime. Path A already
contains the deterministic Python generator; Path C already contains the web
viewer. The runtime connects them without allowing evidence, an LLM, or a raw
sensor to mutate grammar or execute an external effect directly.

## Stack

- Python 3.12: contracts, state machine, policy, audit and sleep cycle.
- Existing Python CKK core: deterministic constraint generation.
- TypeScript + D3/WebGL: live graph and lineage inspection.
- SQLite/Postgres event storage: next persistence step after the in-memory
  contracts are frozen.
- Rust: optional later port for hot deterministic expansion only.

## Sensory and effect boundary

```text
Sensor
  -> IngressPolicy
  -> immutable Observation
  -> planner/LLM proposes Intent
  -> CapabilityPolicy
  -> intent-bound human Approval
  -> sealed Actuator registry
  -> simulated Effect
  -> NREM flush
  -> REM invariant verification
  -> append-only MemoryCommit
```

The MVP has no shell actuator, no open network actuator, no self-modifying
capability route and no real external writes. `SimulationActuator` records what
would have happened. A sensor cannot invoke it. An LLM can only return an
untrusted `Intent`.

## Invariants

- Only admitted sensor IDs and observation kinds cross ingress.
- Payload size, trust threshold and replay IDs are checked.
- One unresolved intent at a time.
- Capabilities are fixed when the runtime is constructed.
- Side effects require approval bound to the exact intent hash.
- Wake cycles have an effect budget.
- Sensors and actuators are closed during NREM and REM.
- Sleep cannot begin with an unresolved intent.
- REM commits only after the append-only audit hash chain validates.
- Halt is fail-closed and has no runtime restart method.

## Running the contained slice

```bash
python3 experiments/sovereign_runtime_demo.py
python3 -m unittest test.test_sovereign_runtime -v
```

The demo reads a simulated temperature observation, proposes cooling, obtains
intent-bound approval, records a simulation-only effect, sleeps, verifies the
audit chain and wakes with one irreversible memory commit.
