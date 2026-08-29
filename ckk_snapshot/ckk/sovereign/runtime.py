"""Contained sensory/runtime slice for the Sovereign Fixpoint Architecture.

Sensors never call actuators.  A planner (LLM or deterministic function) may
only propose an Intent.  Policy, approval and a sealed capability registry sit
between proposal and effect.  The first usable actuator is simulation-only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Mapping, Protocol


def _canonical(value: Any) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


class RuntimePhase(str, Enum):
    WAKE = "WAKE"
    NREM = "NREM"
    REM = "REM"
    HALTED = "HALTED"


@dataclass(frozen=True)
class Observation:
    observation_id: str
    sensor: str
    kind: str
    payload: Mapping[str, Any]
    trust: float


@dataclass(frozen=True)
class Intent:
    action: str
    capability: str
    payload: Mapping[str, Any]
    reason: str

    @property
    def intent_id(self) -> str:
        return _digest(self)


@dataclass(frozen=True)
class Approval:
    intent_id: str
    approved_by: str


@dataclass(frozen=True)
class Effect:
    intent_id: str
    capability: str
    success: bool
    simulated: bool
    output: Mapping[str, Any]


@dataclass(frozen=True)
class MemoryCommit:
    sequence: int
    previous_commit: str
    commit_id: str
    observation_ids: tuple[str, ...]
    effect_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    kind: str
    payload_digest: str
    previous_hash: str
    event_hash: str


@dataclass
class AuditLog:
    events: list[AuditEvent] = field(default_factory=list)
    head: str = "0" * 64

    def append(self, kind: str, payload: Any) -> AuditEvent:
        sequence = len(self.events) + 1
        payload_digest = _digest(payload)
        event_hash = _digest(
            {
                "sequence": sequence,
                "kind": kind,
                "payload_digest": payload_digest,
                "previous_hash": self.head,
            }
        )
        event = AuditEvent(sequence, kind, payload_digest, self.head, event_hash)
        self.events.append(event)
        self.head = event_hash
        return event

    def valid(self) -> bool:
        previous = "0" * 64
        for sequence, event in enumerate(self.events, 1):
            expected = _digest(
                {
                    "sequence": sequence,
                    "kind": event.kind,
                    "payload_digest": event.payload_digest,
                    "previous_hash": previous,
                }
            )
            if event.sequence != sequence or event.previous_hash != previous:
                return False
            if event.event_hash != expected:
                return False
            previous = event.event_hash
        return previous == self.head


@dataclass(frozen=True)
class IngressPolicy:
    sensors: frozenset[str]
    kinds: frozenset[str]
    minimum_trust: float = 0.5
    maximum_payload_bytes: int = 4096

    def validate(self, observation: Observation) -> None:
        if observation.sensor not in self.sensors:
            raise PermissionError("sensor is not admitted")
        if observation.kind not in self.kinds:
            raise PermissionError("observation kind is not admitted")
        if not 0.0 <= observation.trust <= 1.0 or observation.trust < self.minimum_trust:
            raise PermissionError("observation trust is below threshold")
        if len(_canonical(observation.payload).encode()) > self.maximum_payload_bytes:
            raise ValueError("observation payload exceeds ingress budget")


@dataclass(frozen=True)
class CapabilityPolicy:
    allowed: frozenset[str]
    approval_required: frozenset[str] = frozenset()
    maximum_effects_per_wake: int = 4


class Actuator(Protocol):
    capability: str

    def execute(self, intent: Intent) -> Effect: ...


@dataclass
class SimulationActuator:
    """Records the requested effect without touching an external system."""

    capability: str
    effects: list[Effect] = field(default_factory=list)

    def execute(self, intent: Intent) -> Effect:
        effect = Effect(
            intent_id=intent.intent_id,
            capability=self.capability,
            success=True,
            simulated=True,
            output={"would_execute": intent.action, "payload": dict(intent.payload)},
        )
        self.effects.append(effect)
        return effect


Planner = Callable[[tuple[Observation, ...], tuple[MemoryCommit, ...]], Intent | None]


@dataclass
class SovereignRuntime:
    ingress: IngressPolicy
    capabilities: CapabilityPolicy
    actuators: Mapping[str, Actuator]
    phase: RuntimePhase = RuntimePhase.WAKE
    inbox: list[Observation] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    memory: list[MemoryCommit] = field(default_factory=list)
    audit: AuditLog = field(default_factory=AuditLog)
    pending_intent: Intent | None = None
    _seen_observations: set[str] = field(default_factory=set)
    _effects_this_wake: int = 0

    def __post_init__(self) -> None:
        # Copy the registry: callers cannot add a capability after construction.
        self.actuators = dict(self.actuators)
        if set(self.actuators) != set(self.capabilities.allowed):
            raise ValueError("actuator registry must exactly match allowed capabilities")
        for name, actuator in self.actuators.items():
            if actuator.capability != name:
                raise ValueError("actuator capability does not match registry key")

    def halt(self, reason: str) -> None:
        self.audit.append("HALT", {"reason": reason})
        self.pending_intent = None
        self.phase = RuntimePhase.HALTED

    def sense(self, observation: Observation) -> None:
        if self.phase is not RuntimePhase.WAKE:
            raise RuntimeError("sensors are closed outside WAKE")
        self.ingress.validate(observation)
        if observation.observation_id in self._seen_observations:
            raise ValueError("duplicate observation")
        self._seen_observations.add(observation.observation_id)
        self.inbox.append(observation)
        self.audit.append("OBSERVATION", observation)

    def deliberate(self, planner: Planner) -> Intent | None:
        if self.phase is not RuntimePhase.WAKE:
            raise RuntimeError("deliberation requires WAKE")
        if self.pending_intent is not None:
            raise RuntimeError("one unresolved intent is already pending")
        intent = planner(tuple(self.inbox), tuple(self.memory))
        if intent is None:
            self.audit.append("DELIBERATE_SILENCE", {"observations": len(self.inbox)})
            return None
        if not isinstance(intent, Intent):
            raise TypeError("planner must return Intent or None")
        self.pending_intent = intent
        self.audit.append("INTENT_PROPOSED", intent)
        return intent

    def execute(self, approval: Approval | None = None) -> Effect:
        if self.phase is not RuntimePhase.WAKE:
            raise RuntimeError("actuators are closed outside WAKE")
        intent = self.pending_intent
        if intent is None:
            raise RuntimeError("no pending intent")
        if intent.capability not in self.capabilities.allowed:
            self.audit.append("INTENT_DENIED", {"intent": intent, "reason": "capability"})
            self.pending_intent = None
            raise PermissionError("capability is not allowed")
        if self._effects_this_wake >= self.capabilities.maximum_effects_per_wake:
            self.audit.append("INTENT_DENIED", {"intent": intent, "reason": "budget"})
            self.pending_intent = None
            raise PermissionError("wake effect budget exhausted")
        if intent.capability in self.capabilities.approval_required:
            if approval is None or approval.intent_id != intent.intent_id:
                raise PermissionError("intent-bound human approval required")
        actuator = self.actuators[intent.capability]
        try:
            effect = actuator.execute(intent)
        except Exception as exc:
            self.audit.append("EFFECT_FAILED", {"intent": intent, "error_type": type(exc).__name__})
            self.pending_intent = None
            raise
        self.effects.append(effect)
        self._effects_this_wake += 1
        self.pending_intent = None
        self.audit.append("EFFECT", effect)
        return effect

    def sleep(self) -> MemoryCommit:
        """NREM flush followed by REM invariant verification and commit."""
        if self.phase is not RuntimePhase.WAKE:
            raise RuntimeError("sleep can start only from WAKE")
        if self.pending_intent is not None:
            raise RuntimeError("unresolved intent blocks consolidation")
        self.phase = RuntimePhase.NREM
        observation_ids = tuple(item.observation_id for item in self.inbox)
        effect_ids = tuple(item.intent_id for item in self.effects)
        self.audit.append("NREM_FLUSH", {"observations": observation_ids, "effects": effect_ids})

        self.phase = RuntimePhase.REM
        if not self.audit.valid():
            self.halt("audit invariant failed")
            raise RuntimeError("REM rejected invalid audit chain")
        previous = self.memory[-1].commit_id if self.memory else "0" * 64
        sequence = len(self.memory) + 1
        commit_id = _digest(
            {
                "sequence": sequence,
                "previous": previous,
                "observations": observation_ids,
                "effects": effect_ids,
                "audit_head": self.audit.head,
            }
        )
        commit = MemoryCommit(sequence, previous, commit_id, observation_ids, effect_ids)
        self.memory.append(commit)
        self.audit.append("REM_COMMIT", commit)

        self.inbox.clear()
        self.effects.clear()
        self._effects_this_wake = 0
        self.phase = RuntimePhase.WAKE
        return commit
