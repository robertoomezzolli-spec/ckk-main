"""Bootstrap organism: body and laws, but no prescribed persona or language."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Protocol

from .learning import HystereticLearner, LearningProposal
from .runtime import Approval, Effect, Intent, MemoryCommit, Observation, SovereignRuntime


@dataclass(frozen=True)
class BootstrapLaws:
    """Viability constraints, not a character prompt."""

    preserve_continuity: bool = True
    integrate_before_commit: bool = True
    verify_before_persist: bool = True
    action_is_optional: bool = True
    capabilities_are_not_learnable: bool = True

    @property
    def law_hash(self) -> str:
        encoded = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class CognitionResult:
    intent: Intent | None = None
    learning: tuple[LearningProposal, ...] = ()
    salience: float = 0.0


class Cognition(Protocol):
    """Provider-neutral brain. It may speak, stay silent and propose learning."""

    def reflect(
        self,
        observations: tuple[Observation, ...],
        memory: tuple[MemoryCommit, ...],
        learned_context: dict,
        laws: BootstrapLaws,
    ) -> CognitionResult: ...


@dataclass(frozen=True)
class OrganismCommit:
    sequence: int
    runtime_commit: str
    learning_head: str
    previous_identity: str
    identity: str


@dataclass
class SovereignOrganism:
    runtime: SovereignRuntime
    cognition: Cognition
    learner: HystereticLearner = field(default_factory=HystereticLearner)
    laws: BootstrapLaws = field(default_factory=BootstrapLaws)
    identity: str = "0" * 64
    identity_history: list[OrganismCommit] = field(default_factory=list)
    _pending_learning: list[LearningProposal] = field(default_factory=list)

    def perceive(self, observation: Observation) -> None:
        self.runtime.sense(observation)

    def clock_tick(self, tick_id: str, unix_time: int) -> None:
        """Time is a sense. It permits thought without an inbound user message."""
        self.perceive(
            Observation(
                observation_id=tick_id,
                sensor="internal.clock",
                kind="clock.tick",
                payload={"unix_time": unix_time},
                trust=1.0,
            )
        )

    def think(self, approval: Approval | None = None) -> Effect | None:
        if self.runtime.pending_intent is not None:
            raise RuntimeError("cannot reflect with an unresolved prior intent")
        result = self.cognition.reflect(
            tuple(self.runtime.inbox),
            tuple(self.runtime.memory),
            self.learner.context(),
            self.laws,
        )
        if not isinstance(result, CognitionResult):
            raise TypeError("cognition must return CognitionResult")
        if not 0.0 <= result.salience <= 1.0:
            raise ValueError("salience must be in [0, 1]")
        current_evidence = {item.observation_id for item in self.runtime.inbox}
        for proposal in result.learning:
            self.learner.validate(proposal)
            if not set(proposal.evidence_ids).issubset(current_evidence):
                raise PermissionError("learning cites evidence outside current wake history")
        self._pending_learning.extend(result.learning)
        intent = self.runtime.deliberate(lambda observations, memory: result.intent)
        if intent is None:
            return None
        return self.runtime.execute(approval)

    def sleep(self) -> OrganismCommit:
        """Commit runtime history, then admit only learning grounded in that wake."""
        wake_evidence = {item.observation_id for item in self.runtime.inbox}
        for proposal in self._pending_learning:
            if not set(proposal.evidence_ids).issubset(wake_evidence):
                raise PermissionError("learning cites evidence outside current wake history")
        runtime_commit = self.runtime.sleep()
        admitted_evidence = set(runtime_commit.observation_ids)
        for proposal in self._pending_learning:
            if not set(proposal.evidence_ids).issubset(admitted_evidence):
                raise RuntimeError("committed wake differs from preverified learning evidence")
            self.learner.consolidate(proposal)
        self._pending_learning.clear()
        sequence = len(self.identity_history) + 1
        new_identity = hashlib.sha256(
            json.dumps(
                {
                    "sequence": sequence,
                    "previous_identity": self.identity,
                    "runtime_commit": runtime_commit.commit_id,
                    "learning_head": self.learner.head,
                    "law_hash": self.laws.law_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        commit = OrganismCommit(
            sequence=sequence,
            runtime_commit=runtime_commit.commit_id,
            learning_head=self.learner.head,
            previous_identity=self.identity,
            identity=new_identity,
        )
        self.identity_history.append(commit)
        self.identity = new_identity
        return commit
