"""One contained sense -> think -> simulate -> sleep cycle."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))

from ckk.sovereign.runtime import (  # noqa: E402
    Approval,
    CapabilityPolicy,
    IngressPolicy,
    Intent,
    Observation,
    SimulationActuator,
    SovereignRuntime,
)


def planner(observations, memory):
    temperature = observations[-1].payload["temperature_c"]
    return Intent(
        action="propose_cooling" if temperature > 28 else "keep_state",
        capability="simulation.environment",
        payload={"temperature_c": temperature, "delta_c": -2 if temperature > 28 else 0},
        reason="maintain configured thermal corridor",
    )


def run_demo():
    actuator = SimulationActuator("simulation.environment")
    runtime = SovereignRuntime(
        ingress=IngressPolicy(frozenset({"lab.temperature"}), frozenset({"measurement"})),
        capabilities=CapabilityPolicy(
            allowed=frozenset({"simulation.environment"}),
            approval_required=frozenset({"simulation.environment"}),
        ),
        actuators={"simulation.environment": actuator},
    )
    runtime.sense(
        Observation("obs-001", "lab.temperature", "measurement", {"temperature_c": 31}, 0.99)
    )
    intent = runtime.deliberate(planner)
    effect = runtime.execute(Approval(intent.intent_id, "human:roberto"))
    commit = runtime.sleep()
    return {
        "intent": asdict(intent),
        "effect": asdict(effect),
        "memory_commit": asdict(commit),
        "phase": runtime.phase.value,
        "audit_valid": runtime.audit.valid(),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True))
