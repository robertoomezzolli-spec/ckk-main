"""Hysteretic self-learning for committed conversational meaning.

Learning changes beliefs and preferences through evidence-bearing commits.  It
cannot alter grammar, capabilities, recipients or safety policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any


PROTECTED_PREFIXES = ("capability.", "grammar.", "recipient.", "safety.", "actuator.")


def _digest(value: Any) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class LearningProposal:
    key: str
    value: Any
    confidence: float
    evidence_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class Belief:
    key: str
    value: Any
    confidence: float
    evidence_ids: tuple[str, ...]
    commit_id: str
    previous_commit: str


@dataclass
class HystereticLearner:
    admission_threshold: float = 0.70
    replacement_hysteresis: float = 0.15
    beliefs: dict[str, Belief] = field(default_factory=dict)
    history: list[Belief] = field(default_factory=list)
    head: str = "0" * 64

    def validate(self, proposal: LearningProposal) -> None:
        """Fail closed before any proposed action can cause an external effect."""
        if proposal.key.startswith(PROTECTED_PREFIXES):
            raise PermissionError("learning cannot mutate protected architecture")
        if not proposal.evidence_ids:
            raise ValueError("learning requires committed evidence")
        if not 0.0 <= proposal.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    def consolidate(self, proposal: LearningProposal) -> Belief | None:
        self.validate(proposal)
        current = self.beliefs.get(proposal.key)
        if current is None:
            if proposal.confidence < self.admission_threshold:
                return None
        elif proposal.value == current.value:
            # Same-value evidence may strengthen confidence without a switch.
            if proposal.confidence <= current.confidence:
                return None
        elif proposal.confidence < current.confidence + self.replacement_hysteresis:
            return None
        commit_id = _digest(
            {
                "previous": self.head,
                "proposal": proposal,
                "replaces": current.commit_id if current else None,
            }
        )
        belief = Belief(
            key=proposal.key,
            value=proposal.value,
            confidence=proposal.confidence,
            evidence_ids=proposal.evidence_ids,
            commit_id=commit_id,
            previous_commit=self.head,
        )
        self.beliefs[proposal.key] = belief
        self.history.append(belief)
        self.head = commit_id
        return belief

    def context(self) -> dict[str, Any]:
        """Read-only prompt context; committed meaning only, no raw cache."""
        return {key: belief.value for key, belief in sorted(self.beliefs.items())}
