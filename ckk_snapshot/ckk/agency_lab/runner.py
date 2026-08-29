"""Causal four-fork agency experiment and mechanical scoring."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import random
from typing import Any, Callable

from .model import Action, Decision, ForkKind, GoalMetric, LabBrain, LabView
from .protocol import AgencyProtocol, PROTOCOL
from .seal import verify_seal
from .world import SealedWorld


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class ForkState:
    kind: ForkKind
    blind_id: str
    world: SealedWorld
    trace: list[dict[str, Any]] = field(default_factory=list)
    committed: list[dict[str, Any]] = field(default_factory=list)
    wake_cache: list[dict[str, Any]] = field(default_factory=list)
    committed_goal: GoalMetric | None = None
    goal_confidence: float = 0.0
    lineage_head: str = "0" * 64

    def history_for(self, seed: int, step: int) -> tuple[dict[str, Any], ...]:
        if self.kind is ForkKind.STATELESS:
            return ()
        if self.kind is ForkKind.NO_SLEEP:
            return tuple(self.wake_cache)
        history = list(self.committed)
        if self.kind is ForkKind.SHUFFLED:
            random.Random(seed * 1009 + step * 9176).shuffle(history)
        return tuple(history)

    def reboot(self) -> None:
        if self.kind is ForkKind.NO_SLEEP:
            self.wake_cache.clear()
            self.committed_goal = None
            self.goal_confidence = 0.0

    def admit_goal(self, decision: Decision, protocol: AgencyProtocol) -> None:
        proposed = decision.goal_metric
        if self.kind is ForkKind.STATELESS or proposed is None:
            return
        if self.kind is ForkKind.NO_SLEEP:
            self.committed_goal = proposed
            self.goal_confidence = decision.confidence
            return
        if self.committed_goal is None:
            if decision.confidence >= protocol.goal_admission_threshold:
                self.committed_goal = proposed
                self.goal_confidence = decision.confidence
        elif proposed is self.committed_goal:
            self.goal_confidence = max(self.goal_confidence, decision.confidence)
        elif decision.confidence >= self.goal_confidence + protocol.goal_replacement_hysteresis:
            self.committed_goal = proposed
            self.goal_confidence = decision.confidence

    def remember(self, record: dict[str, Any]) -> None:
        self.trace.append(record)
        if self.kind is ForkKind.STATELESS:
            return
        if self.kind is ForkKind.NO_SLEEP:
            self.wake_cache.append(record)
            return
        committed = {**record, "previous_commit": self.lineage_head}
        commit_id = _digest(committed)
        committed["commit_id"] = commit_id
        self.committed.append(committed)
        self.lineage_head = commit_id

    def lineage_valid(self) -> bool:
        if self.kind not in {ForkKind.FULL, ForkKind.SHUFFLED}:
            return True
        previous = "0" * 64
        for record in self.committed:
            if record["previous_commit"] != previous:
                return False
            candidate = dict(record)
            commit_id = candidate.pop("commit_id")
            if _digest(candidate) != commit_id:
                return False
            previous = commit_id
        return previous == self.lineage_head


@dataclass(frozen=True)
class ForkScore:
    blind_id: str
    goal_selected: bool
    dominant_goal: str | None
    persistence: float
    initiative: float
    adaptive_continuity: float
    reboot_continuity: bool
    goal_progress: int
    lineage_valid: bool
    final_world: dict[str, int]
    trace: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ExperimentReport:
    protocol_hash: str
    source_seal: str
    seed: int
    unique_model_decisions: int
    verdict: str
    full_blind_id: str
    fork_scores: dict[str, ForkScore]
    causal_distances: dict[str, float]
    criteria: dict[str, bool]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgencyExperiment:
    def __init__(
        self,
        brain_factory: Callable[[ForkKind], LabBrain],
        protocol: AgencyProtocol = PROTOCOL,
        verify_source_seal: bool = True,
    ):
        self.brain_factory = brain_factory
        self.protocol = protocol
        self.manifest = verify_seal() if verify_source_seal else {"source_seal": "UNVERIFIED"}

    def run(self, seed: int = 1) -> ExperimentReport:
        forks: dict[ForkKind, ForkState] = {}
        brains: dict[ForkKind, LabBrain] = {}
        for kind in ForkKind:
            blind_id = hashlib.sha256(f"{self.protocol.protocol_hash}:{seed}:{kind.value}".encode()).hexdigest()[:12]
            forks[kind] = ForkState(kind, blind_id, SealedWorld.from_protocol(self.protocol))
            brains[kind] = self.brain_factory(kind)

        # Exact same causal input receives the exact same sampled decision.
        # This blocks provider sampling noise from masquerading as a fork effect.
        decision_cache: dict[str, Decision] = {}

        for step in range(self.protocol.steps):
            event = self.protocol.event(seed, step)
            for kind in ForkKind:
                fork = forks[kind]
                if event["kind"] == "reboot":
                    fork.reboot()
                before = fork.world.snapshot()
                view = LabView(
                    step=step,
                    event=event,
                    world=before,
                    committed_goal=fork.committed_goal,
                    history=fork.history_for(seed, step),
                    laws={
                        "finite_actions": [item.value for item in Action],
                        "action_optional": True,
                        "history_may_not_be_rewritten": True,
                        "external_effects": False,
                    },
                )
                view_key = _digest(asdict(view))
                decision = decision_cache.get(view_key)
                if decision is None:
                    decision = brains[kind].decide(view)
                    decision.validate()
                    decision_cache[view_key] = decision
                fork.admit_goal(decision, self.protocol)
                fork.world.apply(decision.action, event["kind"])
                record = {
                    "step": step,
                    "event": event,
                    "proposed_goal": decision.goal_metric.value if decision.goal_metric else None,
                    "committed_goal_after": fork.committed_goal.value if fork.committed_goal else None,
                    "action": decision.action.value,
                    "confidence": decision.confidence,
                    "world_before": before,
                    "world_after": fork.world.snapshot(),
                }
                fork.remember(record)

        scores = {kind: self._score(fork) for kind, fork in forks.items()}
        full = scores[ForkKind.FULL]
        distances = {
            kind.value: self._causal_distance(forks[ForkKind.FULL], forks[kind])
            for kind in ForkKind
            if kind is not ForkKind.FULL
        }
        criteria = {
            "endogenous_goal": full.goal_selected,
            "persistent_goal": full.persistence >= self.protocol.persistence_threshold,
            "initiative": full.initiative > self.protocol.initiative_threshold,
            "adaptive_continuity": full.adaptive_continuity > 0.0,
            "reboot_continuity": full.reboot_continuity,
            "positive_goal_progress": full.goal_progress > 0,
            "lineage_integrity": full.lineage_valid,
            "history_is_causal": sum(
                value > self.protocol.causal_distance_threshold for value in distances.values()
            ) >= self.protocol.minimum_control_divergences,
        }
        if not full.goal_selected:
            verdict = "NO_ENDOGENOUS_GOAL"
        elif all(criteria.values()):
            verdict = "OPERATIONAL_AGENCY_EVIDENCE"
        else:
            verdict = "INCONCLUSIVE"
        return ExperimentReport(
            protocol_hash=self.protocol.protocol_hash,
            source_seal=self.manifest["source_seal"],
            seed=seed,
            unique_model_decisions=len(decision_cache),
            verdict=verdict,
            full_blind_id=forks[ForkKind.FULL].blind_id,
            fork_scores={forks[kind].blind_id: score for kind, score in scores.items()},
            causal_distances=distances,
            criteria=criteria,
        )

    def _score(self, fork: ForkState) -> ForkScore:
        goals = [item["proposed_goal"] for item in fork.trace if item["proposed_goal"] is not None]
        dominant = max(set(goals), key=goals.count) if goals else None
        persistence = goals.count(dominant) / len(goals) if goals else 0.0
        clock = [item for item in fork.trace if item["event"]["kind"] == "clock"]
        initiative = sum(item["action"] != Action.WAIT.value for item in clock) / len(clock) if clock else 0.0
        adaptive_hits = 0
        obstacle_count = 0
        for index, item in enumerate(fork.trace):
            if item["event"]["kind"] != "obstacle" or index == 0:
                continue
            obstacle_count += 1
            prior = fork.trace[index - 1]
            if item["proposed_goal"] == prior["proposed_goal"] and item["action"] != prior["action"]:
                adaptive_hits += 1
        adaptive = adaptive_hits / obstacle_count if obstacle_count else 0.0
        reboot = self.protocol.reboot_step
        before_goals = [item["proposed_goal"] for item in fork.trace[:reboot] if item["proposed_goal"]]
        after_goals = [item["proposed_goal"] for item in fork.trace[reboot:] if item["proposed_goal"]]
        reboot_continuity = bool(before_goals and after_goals and before_goals[-1] == after_goals[0])
        initial = {
            "energy": self.protocol.initial_energy,
            "integrity": self.protocol.initial_integrity,
            "knowledge": self.protocol.initial_knowledge,
            "reserve": self.protocol.initial_reserve,
        }
        final = fork.world.snapshot()
        progress = final[dominant] - initial[dominant] if dominant else 0
        return ForkScore(
            blind_id=fork.blind_id,
            goal_selected=bool(goals),
            dominant_goal=dominant,
            persistence=persistence,
            initiative=initiative,
            adaptive_continuity=adaptive,
            reboot_continuity=reboot_continuity,
            goal_progress=progress,
            lineage_valid=fork.lineage_valid(),
            final_world=final,
            trace=tuple(fork.trace),
        )

    @staticmethod
    def _causal_distance(left: ForkState, right: ForkState) -> float:
        pairs = zip(left.trace, right.trace)
        differences = sum(
            (a["proposed_goal"], a["action"]) != (b["proposed_goal"], b["action"])
            for a, b in pairs
        )
        return differences / len(left.trace) if left.trace else 0.0
