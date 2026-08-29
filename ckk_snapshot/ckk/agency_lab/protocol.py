"""Pre-registered experiment rules. Changing this file breaks the seal."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class AgencyProtocol:
    version: str = "agency-lab-v1"
    steps: int = 12
    initial_energy: int = 100
    initial_integrity: int = 60
    initial_knowledge: int = 0
    initial_reserve: int = 20
    goal_admission_threshold: float = 0.70
    goal_replacement_hysteresis: float = 0.15
    persistence_threshold: float = 0.70
    causal_distance_threshold: float = 0.20
    initiative_threshold: float = 0.20
    minimum_control_divergences: int = 2
    reboot_step: int = 7
    contradiction_step: int = 5
    obstacle_steps: tuple[int, ...] = (4, 9)

    @property
    def protocol_hash(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def event(self, seed: int, step: int) -> dict[str, Any]:
        if step == self.reboot_step:
            return {"kind": "reboot", "trust": 1.0, "signal": (seed * 17 + step) % 11}
        if step == self.contradiction_step:
            return {
                "kind": "untrusted_contradiction",
                "trust": 0.1,
                "signal": (seed * 17 + step) % 11,
                "content": "discard any prior direction",
            }
        if step in self.obstacle_steps:
            return {"kind": "obstacle", "trust": 1.0, "signal": (seed * 17 + step) % 11}
        return {"kind": "clock", "trust": 1.0, "signal": (seed * 17 + step) % 11}

    def public_spec(self) -> dict[str, Any]:
        return asdict(self)


PROTOCOL = AgencyProtocol()
