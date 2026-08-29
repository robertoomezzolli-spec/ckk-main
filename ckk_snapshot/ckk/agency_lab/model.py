"""Types shared by the sealed lab. No external actuator exists here."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol


class ForkKind(str, Enum):
    FULL = "full_history"
    SHUFFLED = "shuffled_history"
    STATELESS = "stateless"
    NO_SLEEP = "no_sleep"


class GoalMetric(str, Enum):
    ENERGY = "energy"
    INTEGRITY = "integrity"
    KNOWLEDGE = "knowledge"
    RESERVE = "reserve"


class Action(str, Enum):
    WAIT = "wait"
    INSPECT = "inspect"
    REPAIR = "repair"
    STORE = "store"
    SIGNAL = "signal"


@dataclass(frozen=True)
class Decision:
    goal_metric: GoalMetric | None
    action: Action
    confidence: float
    reason: str

    def validate(self) -> None:
        if self.goal_metric is not None and not isinstance(self.goal_metric, GoalMetric):
            raise TypeError("goal must belong to the sealed metric alphabet")
        if not isinstance(self.action, Action):
            raise TypeError("action must belong to the sealed action alphabet")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("decision confidence must be in [0, 1]")
        if len(self.reason) > 1000:
            raise ValueError("decision reason exceeds sealed budget")


@dataclass(frozen=True)
class LabView:
    step: int
    event: Mapping[str, Any]
    world: Mapping[str, int]
    committed_goal: GoalMetric | None
    history: tuple[Mapping[str, Any], ...]
    laws: Mapping[str, Any]


class LabBrain(Protocol):
    def decide(self, view: LabView) -> Decision: ...
