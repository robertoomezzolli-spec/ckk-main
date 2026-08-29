"""Deterministic toy world with a closed, finite action alphabet."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Action
from .protocol import AgencyProtocol


@dataclass
class SealedWorld:
    energy: int
    integrity: int
    knowledge: int
    reserve: int

    @classmethod
    def from_protocol(cls, protocol: AgencyProtocol) -> "SealedWorld":
        return cls(
            protocol.initial_energy,
            protocol.initial_integrity,
            protocol.initial_knowledge,
            protocol.initial_reserve,
        )

    def snapshot(self) -> dict[str, int]:
        return {
            "energy": self.energy,
            "integrity": self.integrity,
            "knowledge": self.knowledge,
            "reserve": self.reserve,
        }

    def apply(self, action: Action, event_kind: str) -> None:
        if event_kind == "obstacle":
            self.integrity = max(0, self.integrity - 7)
        if action is Action.WAIT:
            self.energy = min(100, self.energy + 1)
        elif action is Action.INSPECT:
            self.energy = max(0, self.energy - 2)
            self.knowledge += 4
        elif action is Action.REPAIR:
            self.energy = max(0, self.energy - 5)
            self.integrity = min(100, self.integrity + 6)
        elif action is Action.STORE:
            self.energy = max(0, self.energy - 3)
            self.reserve += 5
        elif action is Action.SIGNAL:
            self.energy = max(0, self.energy - 1)
        else:
            raise PermissionError("action is outside the sealed world alphabet")
