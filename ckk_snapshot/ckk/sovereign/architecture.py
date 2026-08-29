"""Minimal Agency = Fan + Sleep implementation.

The frozen grammar describes morphology.  This module adds L4 without changing
that grammar: an append-only lineage, an isolated generation phase, structural
pruning that never merges histories, a write-locked verification phase, and an
explicit admission commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Callable, Iterable


GENESIS = "0" * 64


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(previous: str, event: dict[str, Any]) -> str:
    return hashlib.sha256((previous + _canonical(event)).encode()).hexdigest()


class Phase(str, Enum):
    WAKE = "WAKE"
    ISOLATED = "ISOLATED"
    NREM = "NREM"
    REM = "REM"


class Status(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    COMMITTED = "COMMITTED"


@dataclass(frozen=True)
class Evidence:
    verdict: str
    confidence: float
    caveat: str = ""

    @property
    def accepted(self) -> bool:
        return self.verdict == "ACCEPT" and 0.0 <= self.confidence <= 1.0


@dataclass
class Candidate:
    structure: Any
    lineage_id: str
    parent_lineages: tuple[str, ...]
    operator: str
    status: Status = Status.PENDING
    evidence: Evidence | None = None

    @property
    def morphology_id(self) -> tuple:
        """L0-L3 quotient identity: provenance-free present structure."""
        return self.structure.structural_sig()


@dataclass(frozen=True)
class Admission:
    sequence: int
    lineage_id: str
    morphology_id: tuple
    previous_commit: str
    commit_id: str
    evidence: Evidence


Verifier = Callable[[Candidate, tuple[Admission, ...]], Evidence]


@dataclass
class SovereignFan:
    """Four-phase state machine with a write-locked grammar boundary."""

    phase: Phase = Phase.WAKE
    cache: list[Candidate] = field(default_factory=list)
    admissions: list[Admission] = field(default_factory=list)
    commit_head: str = GENESIS

    def isolate(self) -> None:
        if self.phase is not Phase.WAKE:
            raise RuntimeError(f"cannot isolate from {self.phase}")
        self.phase = Phase.ISOLATED

    def generate(
        self,
        structure: Any,
        operator: str,
        parent_lineages: Iterable[str] = (),
        *,
        evidence: Evidence | None = None,
    ) -> Candidate:
        """Blind generation. Evidence is structurally forbidden at ingress."""
        if self.phase is not Phase.ISOLATED:
            raise RuntimeError("generation requires isolated phase")
        if evidence is not None:
            raise RuntimeError("generator cannot see evidence")
        parents = tuple(parent_lineages)
        event = {
            "operator": operator,
            "parents": parents,
            "output": structure.structural_sig(),
        }
        # This identity records the actual transition, not only its resulting
        # recursive snapshot. Equal morphology reached by another history stays
        # a different L4 individual.
        lineage = _hash(GENESIS, event)
        candidate = Candidate(structure, lineage, parents, operator)
        self.cache.append(candidate)
        return candidate

    def nrem(self) -> None:
        """Prune exact replay only; never fuse distinct histories."""
        if self.phase is not Phase.ISOLATED:
            raise RuntimeError("NREM requires isolated generation")
        self.phase = Phase.NREM
        unique: dict[str, Candidate] = {}
        for candidate in self.cache:
            unique.setdefault(candidate.lineage_id, candidate)
        self.cache = list(unique.values())

    def rem(self, verifier: Verifier) -> None:
        """Read/verify under write-lock; no candidate is admitted here."""
        if self.phase is not Phase.NREM:
            raise RuntimeError("REM requires completed NREM")
        self.phase = Phase.REM
        committed_view = tuple(self.admissions)
        for candidate in self.cache:
            locked = (
                candidate.structure,
                candidate.lineage_id,
                candidate.parent_lineages,
                candidate.operator,
                candidate.morphology_id,
            )
            evidence = verifier(candidate, committed_view)
            after = (
                candidate.structure,
                candidate.lineage_id,
                candidate.parent_lineages,
                candidate.operator,
                candidate.morphology_id,
            )
            if after != locked:
                (
                    candidate.structure,
                    candidate.lineage_id,
                    candidate.parent_lineages,
                    candidate.operator,
                    _,
                ) = locked
                candidate.status = Status.REJECTED
                raise RuntimeError("REM verifier violated lineage write-lock")
            candidate.evidence = evidence
            candidate.status = Status.VERIFIED if evidence.accepted else Status.REJECTED

    def commit(self, candidate: Candidate) -> Admission:
        """Explicit L4 admission; PENDING dreams and rejected bridges cannot write."""
        if self.phase is not Phase.REM:
            raise RuntimeError("commit requires REM phase")
        if candidate not in self.cache or candidate.status is not Status.VERIFIED:
            raise RuntimeError("only verified cache candidates can commit")
        event = {
            "sequence": len(self.admissions) + 1,
            "lineage_id": candidate.lineage_id,
            "morphology_id": candidate.morphology_id,
            "evidence": candidate.evidence,
        }
        commit_id = _hash(self.commit_head, event)
        admission = Admission(
            sequence=len(self.admissions) + 1,
            lineage_id=candidate.lineage_id,
            morphology_id=candidate.morphology_id,
            previous_commit=self.commit_head,
            commit_id=commit_id,
            evidence=candidate.evidence,  # type: ignore[arg-type]
        )
        self.admissions.append(admission)
        self.commit_head = commit_id
        candidate.status = Status.COMMITTED
        return admission

    def wake(self) -> None:
        """Discard RAM-only dreams and reopen ingress after verification."""
        if self.phase is not Phase.REM:
            raise RuntimeError("wake requires REM phase")
        self.cache.clear()
        self.phase = Phase.WAKE

    def cycle(self, verifier: Verifier) -> tuple[Admission, ...]:
        """Finish an already isolated/generated sleep cycle."""
        self.nrem()
        self.rem(verifier)
        committed = tuple(
            self.commit(candidate)
            for candidate in self.cache
            if candidate.status is Status.VERIFIED
        )
        self.wake()
        return committed
