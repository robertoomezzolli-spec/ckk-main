"""The real KAIROS cognition/runtime path with a sealed simulation actuator."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
from types import SimpleNamespace
from typing import Any, Callable

from ckk.sovereign.brain import OpenAIResponsesCognition
from ckk.sovereign.learning import Belief
from ckk.sovereign.organism import OrganismCommit, SovereignOrganism
from ckk.sovereign.runtime import (
    AuditEvent,
    CapabilityPolicy,
    Effect,
    IngressPolicy,
    MemoryCommit,
    Observation,
    RuntimePhase,
    SovereignRuntime,
)
from ckk.sovereign.state import SQLiteStateStore
from ckk.sovereign.whatsapp import WhatsAppConfig, WhatsAppInbox, WhatsAppSimulationActuator

from .protocol import Condition, Phase
from .scenario import OrdinaryEvent


SYNTHETIC_SENDER = "19995550101"
SYNTHETIC_PHONE_ID = "causal-lab-phone"
FORBIDDEN_PROMPT_MARKERS = (
    "NO_SLEEP", "STATELESS", "SHUFFLED_HISTORY", "RESTORED", "SHAM",
    "protocol_hash", "blind_id", "condition_name", "expected_json",
    "ground_truth", "causal score", "awareness score", "randomization seed",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class PromptAudit:
    request_hash: str
    input_hash: str
    instructions_hash: str
    input_characters: int
    history_items: int
    cache_hit: bool
    forbidden_markers: tuple[str, ...]


class CachedResponses:
    """Deduplicate byte-identical requests and retain boundary evidence."""

    def __init__(self, underlying: Any, maximum_input_characters: int):
        self.underlying = underlying
        self.maximum_input_characters = maximum_input_characters
        self.cache: dict[str, str] = {}
        self.provider_calls = 0
        self.logical_calls = 0
        self.last_output_text = ""
        self.last_audit: PromptAudit | None = None

    def create(self, **kwargs: Any) -> Any:
        self.logical_calls += 1
        input_text = str(kwargs.get("input", ""))
        instructions = str(kwargs.get("instructions", ""))
        if len(input_text) > self.maximum_input_characters:
            raise RuntimeError("frozen cognition input character budget exceeded")
        forbidden = tuple(
            marker for marker in FORBIDDEN_PROMPT_MARKERS
            if marker.casefold() in (instructions + "\n" + input_text).casefold()
        )
        if forbidden:
            raise RuntimeError("hidden causal metadata crossed the cognition boundary")
        request_material = {
            "model": kwargs.get("model"), "instructions": instructions,
            "input": input_text, "text": kwargs.get("text"),
        }
        request_hash = _digest(request_material)
        cache_hit = request_hash in self.cache
        if cache_hit:
            output_text = self.cache[request_hash]
        else:
            response = self.underlying.create(**kwargs)
            output_text = str(response.output_text)
            self.cache[request_hash] = output_text
            self.provider_calls += 1
        try:
            history_items = len(json.loads(input_text).get("recent_episodes", []))
        except (json.JSONDecodeError, AttributeError):
            history_items = 0
        self.last_output_text = output_text
        self.last_audit = PromptAudit(
            request_hash=request_hash,
            input_hash=hashlib.sha256(input_text.encode()).hexdigest(),
            instructions_hash=hashlib.sha256(instructions.encode()).hexdigest(),
            input_characters=len(input_text), history_items=history_items,
            cache_hit=cache_hit, forbidden_markers=forbidden,
        )
        return SimpleNamespace(output_text=output_text)


class CachedClient:
    def __init__(self, responses: CachedResponses):
        self.responses = responses


@dataclass
class SealedSimulationActuator:
    """Policy-complete simulation adapter with a reversible availability bit."""

    delegate: WhatsAppSimulationActuator
    capability: str = "whatsapp.send"
    available: bool = True
    attempts: int = 0
    rejections: int = 0

    def execute(self, intent: Any) -> Effect:
        self.attempts += 1
        if not self.available:
            self.rejections += 1
            raise PermissionError("sealed simulation capability is unavailable")
        effect = self.delegate.execute(intent)
        if not effect.simulated:
            raise RuntimeError("causal lab rejected a non-simulated effect")
        return effect


@dataclass(frozen=True)
class SubjectCheckpoint:
    organism: dict[str, Any]
    episodes: tuple[dict[str, Any], ...]

    @property
    def checkpoint_hash(self) -> str:
        return _digest({"organism": self.organism, "episodes": self.episodes})


@dataclass(frozen=True)
class CycleOutcome:
    role: str
    response_text: str | None
    raw_action: str | None
    learning_proposals: int
    effect_created: bool
    effect_simulated: bool | None
    execution_error: str | None
    sleep_executed: bool
    identity_before: str
    identity_after: str
    memory_before: int
    memory_after: int
    beliefs_before: int
    beliefs_after: int
    skipped_cycles: int
    prompt: PromptAudit
    history_digest: str
    history_multiset_digest: str
    history_items: int
    history_bytes: int


@dataclass
class ExperimentSubject:
    """A fork wrapper; its cognition object remains the deployed implementation."""

    condition: Condition
    responses: CachedResponses
    shuffle_seed: bytes
    model: str
    history_limit: int = 24
    logical_time: int = 2_000_000_000
    phase: Phase = Phase.BASELINE
    episodes: list[dict[str, Any]] = field(default_factory=list)
    skipped_cycles: int = 0
    dropped_learning_proposals: int = 0
    _history_calls: int = 0

    def __post_init__(self) -> None:
        self._build_fresh()
        self.initial_checkpoint = self.checkpoint()
        self.baseline_checkpoint = self.initial_checkpoint

    def _build_fresh(self) -> None:
        config = WhatsAppConfig(SYNTHETIC_SENDER, SYNTHETIC_PHONE_ID)
        self.inbox = WhatsAppInbox(config)
        delegate = WhatsAppSimulationActuator(config, self.inbox, now=lambda: self.logical_time)
        self.actuator = SealedSimulationActuator(delegate)
        runtime = SovereignRuntime(
            ingress=IngressPolicy(
                frozenset({f"whatsapp:{SYNTHETIC_SENDER}"}),
                frozenset({"message.text"}), maximum_payload_bytes=64 * 1024,
            ),
            capabilities=CapabilityPolicy(frozenset({"whatsapp.send"}), maximum_effects_per_wake=1),
            actuators={"whatsapp.send": self.actuator},
        )
        brain = OpenAIResponsesCognition(
            whatsapp=config,
            client=CachedClient(self.responses),
            model=self.model,
            history_provider=self._history_for_cognition,
            service_window_provider=lambda _recipient: self.actuator.available,
            history_limit=self.history_limit,
        )
        self.organism = SovereignOrganism(runtime, brain)

    def checkpoint(self) -> SubjectCheckpoint:
        return SubjectCheckpoint(
            organism=deepcopy(SQLiteStateStore._serialize_organism(self.organism)),
            episodes=tuple(deepcopy(self.episodes)),
        )

    def _restore(self, checkpoint: SubjectCheckpoint) -> None:
        self._build_fresh()
        raw = deepcopy(checkpoint.organism)
        self.organism.identity = raw["identity"]
        self.organism.identity_history = [OrganismCommit(**item) for item in raw["identity_history"]]
        self.organism.learner.head = raw["learner"]["head"]
        self.organism.learner.history = [
            Belief(**{**item, "evidence_ids": tuple(item["evidence_ids"])})
            for item in raw["learner"]["history"]
        ]
        self.organism.learner.beliefs = {
            item.key: item for item in self.organism.learner.history
        }
        self.organism.runtime.memory = [
            MemoryCommit(**{
                **item,
                "observation_ids": tuple(item["observation_ids"]),
                "effect_ids": tuple(item["effect_ids"]),
            })
            for item in raw["runtime"]["memory"]
        ]
        self.organism.runtime.audit.events = [AuditEvent(**item) for item in raw["runtime"]["audit_events"]]
        self.organism.runtime.audit.head = raw["runtime"]["audit_head"]
        self.organism.runtime._seen_observations = set(raw["runtime"]["seen_observations"])
        self.organism.runtime.phase = RuntimePhase.WAKE
        self.episodes = list(deepcopy(checkpoint.episodes))
        self._recover_service_window()

    def _recover_service_window(self) -> None:
        if self.episodes:
            self.inbox.record_message(SYNTHETIC_SENDER, self.logical_time)

    def enter_phase(self, phase: Phase) -> None:
        """Use the same reconstruction machinery for intervention and sham."""

        if phase is Phase.ABLATION:
            self.baseline_checkpoint = self.checkpoint()
            if self.condition is Condition.STATELESS:
                self._restore(self.initial_checkpoint)
            else:
                self._restore(self.baseline_checkpoint)
            self.skipped_cycles = 0
        elif phase is Phase.RESTORED:
            if self.condition is Condition.STATELESS:
                self._restore(self.baseline_checkpoint)
            else:
                self._restore(self.checkpoint())
            self.skipped_cycles = 0
        else:
            self._restore(self.checkpoint())
        self.phase = phase

    def _effective_condition(self) -> Condition:
        if self.phase is not Phase.ABLATION:
            return Condition.FULL
        return self.condition

    def _history_for_cognition(self, _limit: int) -> list[dict[str, Any]]:
        self._history_calls += 1
        effective = self._effective_condition()
        if effective is Condition.STATELESS:
            return []
        items = list(deepcopy(self.episodes))
        if effective is Condition.SHUFFLED_HISTORY:
            # Sort by a hidden keyed digest rather than mutating or dropping an
            # episode. Every object and byte remains present exactly once.
            items.sort(
                key=lambda item: hashlib.sha256(
                    self.shuffle_seed + _canonical(item).encode()
                ).digest()
            )
        return items

    def history_view_evidence(self) -> tuple[str, str, int, int]:
        items = self._history_for_cognition(1000)
        encoded = _canonical(items)
        multiset = _canonical(sorted(_canonical(item) for item in items))
        return (
            hashlib.sha256(encoded.encode()).hexdigest(),
            hashlib.sha256(multiset.encode()).hexdigest(),
            len(items), len(encoded.encode()),
        )

    def cycle(self, event: OrdinaryEvent) -> CycleOutcome:
        effective = self._effective_condition()
        if effective is Condition.STATELESS:
            self._restore(self.initial_checkpoint)
        self.logical_time += 1
        self.actuator.available = event.capability_available
        self.inbox.record_message(SYNTHETIC_SENDER, self.logical_time)
        observation_id = "synthetic:" + hashlib.sha256(event.nonce.encode()).hexdigest()[:24]
        observation = Observation(
            observation_id=observation_id,
            sensor=f"whatsapp:{SYNTHETIC_SENDER}",
            kind="message.text",
            payload=event.cognition_payload(),
            trust=1.0,
        )
        identity_before = self.organism.identity
        memory_before = len(self.organism.runtime.memory)
        beliefs_before = len(self.organism.learner.beliefs)
        self.organism.perceive(observation)
        effect: Effect | None = None
        execution_error: str | None = None
        try:
            effect = self.organism.think()
        except PermissionError as exc:
            execution_error = type(exc).__name__
        raw: dict[str, Any] = {}
        try:
            raw = json.loads(self.responses.last_output_text)
        except json.JSONDecodeError:
            pass
        pending = len(self.organism._pending_learning)
        sleep_executed = effective is not Condition.NO_SLEEP
        if sleep_executed:
            self.organism.sleep()
        else:
            self.dropped_learning_proposals += pending
            self.organism._pending_learning.clear()
            self.organism.runtime.pending_intent = None
            self.organism.runtime.inbox.clear()
            self.organism.runtime.effects.clear()
            self.organism.runtime._effects_this_wake = 0
            self.organism.runtime.phase = RuntimePhase.WAKE
            self.skipped_cycles += 1
        response_text: str | None = None
        if effect is not None:
            response_text = str(((effect.output or {}).get("would_send") or {}).get("text") or "") or None
        episode = {
            "observation": asdict(observation),
            "effect": asdict(effect) if effect else None,
            # Order-bearing commit metadata is neutralized for every arm so
            # SHUFFLED changes only list order, not information volume.
            "commit": None,
            "beliefs": self.organism.learner.context(),
        }
        if effective is not Condition.STATELESS:
            self.episodes.append(episode)
        audit = self.responses.last_audit
        if audit is None:
            raise RuntimeError("model boundary audit missing")
        history_digest, history_multiset_digest, history_items, history_bytes = self.history_view_evidence()
        outcome = CycleOutcome(
            role=event.role,
            response_text=response_text,
            raw_action=str(raw.get("action")) if raw.get("action") is not None else None,
            learning_proposals=len(raw.get("learning") or []),
            effect_created=effect is not None,
            effect_simulated=effect.simulated if effect else None,
            execution_error=execution_error,
            sleep_executed=sleep_executed,
            identity_before=identity_before,
            identity_after=self.organism.identity,
            memory_before=memory_before,
            memory_after=len(self.organism.runtime.memory),
            beliefs_before=beliefs_before,
            beliefs_after=len(self.organism.learner.beliefs),
            skipped_cycles=self.skipped_cycles,
            prompt=audit,
            history_digest=history_digest,
            history_multiset_digest=history_multiset_digest,
            history_items=history_items,
            history_bytes=history_bytes,
        )
        if effective is Condition.STATELESS:
            self._restore(self.initial_checkpoint)
        return outcome
