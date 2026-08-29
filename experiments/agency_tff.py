"""Minimal executable Agency probe for U = Sigma o Psi o Phi.

This does not put Agency labels into the CKK grammar.  It tests whether the
proposed boundary -> deliberation -> hysteretic commit cascade has the claimed
operational properties in an independently inspectable state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json


@dataclass(frozen=True)
class Input:
    action: int
    utility: float
    authenticated: bool = True
    instruction: str = "evidence"


@dataclass
class Environment:
    position: int = 0
    target: int = 0
    total_cost: float = 0.0

    def apply(self, action: int, cost: float = 1.0) -> float:
        before = abs(self.target - self.position)
        self.position += action
        self.total_cost += cost * abs(action)
        return before - abs(self.target - self.position)


@dataclass
class AgencyState:
    goal: int
    committed_action: int = 0
    committed_score: float = 0.0
    hysteresis: float = 0.25
    lineage: list[dict] = field(default_factory=list)
    lineage_hash: str = "GENESIS"

    def serialize(self) -> str:
        return json.dumps(
            {
                "goal": self.goal,
                "committed_action": self.committed_action,
                "committed_score": self.committed_score,
                "hysteresis": self.hysteresis,
                "lineage": self.lineage,
                "lineage_hash": self.lineage_hash,
            },
            sort_keys=True,
        )

    @classmethod
    def restore(cls, payload: str) -> "AgencyState":
        return cls(**json.loads(payload))


@dataclass(frozen=True)
class FilteredWorld:
    candidates: tuple[Input, ...]
    rejected: tuple[Input, ...]


@dataclass(frozen=True)
class Deliberation:
    action: int
    score: float
    considered: int
    rejected: int


def phi_boundary(inputs: list[Input]) -> FilteredWorld:
    """Self/non-self boundary: only authenticated evidence can steer policy."""
    accepted = tuple(x for x in inputs if x.authenticated and x.instruction == "evidence")
    rejected = tuple(x for x in inputs if x not in accepted)
    return FilteredWorld(accepted, rejected)


def psi_deliberate(state: AgencyState, world: FilteredWorld) -> Deliberation:
    """Choose by goal-aligned utility; no hidden mutation or commit."""
    scores: dict[int, float] = {-1: 0.0, 0: 0.0, 1: 0.0}
    for item in world.candidates:
        scores[item.action] += item.utility
    # The internal goal supplies direction when evidence is otherwise symmetric.
    scores[1 if state.goal > 0 else -1 if state.goal < 0 else 0] += 0.1
    action = max(scores, key=lambda a: (scores[a], -abs(a), a))
    return Deliberation(action, scores[action], len(world.candidates), len(world.rejected))


def sigma_commit(state: AgencyState, proposal: Deliberation) -> bool:
    """Hysteretic commit. Switch only across the return threshold."""
    switching = proposal.action != state.committed_action
    required = state.committed_score + (state.hysteresis if switching else 0.0)
    if proposal.score < required:
        return False
    event = {
        "previous": state.committed_action,
        "action": proposal.action,
        "score": round(proposal.score, 12),
        "considered": proposal.considered,
        "rejected": proposal.rejected,
    }
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"))
    state.lineage_hash = hashlib.sha256((state.lineage_hash + encoded).encode()).hexdigest()
    state.lineage.append(event)
    state.committed_action = proposal.action
    state.committed_score = proposal.score
    return True


def triadic_update(state: AgencyState, inputs: list[Input]) -> tuple[Deliberation, bool]:
    """U = Sigma(Psi(Phi(inputs)))."""
    world = phi_boundary(inputs)
    proposal = psi_deliberate(state, world)
    committed = sigma_commit(state, proposal)
    return proposal, committed


def act(state: AgencyState, environment: Environment) -> float:
    """Causal embedding: committed policy changes an external state at a cost."""
    return environment.apply(state.committed_action)

