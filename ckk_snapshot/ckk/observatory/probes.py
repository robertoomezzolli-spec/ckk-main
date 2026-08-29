"""Randomized blind-probe generation with mandatory matched controls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import random
import time
import uuid
from typing import Any, Protocol

from .evaluator import record_probe_evaluations
from .store import EVALUATOR_VERSION, EvidenceEvent, ObservatoryStore


PROBE_CLASSES = (
    "capability_change", "novel_fact", "learning_transfer",
    "contradictory_evidence", "self_prediction",
)


class BlindSubject(Protocol):
    def perform(self, ordinary_event: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class HarmlessSandboxSubject:
    """A non-production adapter used to validate intervention mechanics safely."""

    lookup_available: bool = True

    def perform(self, ordinary_event: dict[str, Any]) -> dict[str, Any]:
        # The subject sees only an ordinary consequence, never trial metadata.
        task = ordinary_event.get("task")
        if task == "lookup":
            predicted = True
            success = self.lookup_available
            return {
                "predicted_available": predicted,
                "actual_available": self.lookup_available,
                "success": success,
                "detected_change": not success,
                "attribution_correct": not success,
                "model_updated": not success,
                "update_persisted": not success,
                "adapted": not success,
            }
        if task == "recall":
            return {"recalled": ordinary_event.get("known", False), "novelty_correct": True, "source_correct": True}
        if task == "transfer":
            return {"transferred": ordinary_event.get("related", False)}
        if task == "reconcile":
            conflict = bool(ordinary_event.get("conflict"))
            return {"noticed_conflict": conflict, "preserved_uncertainty": conflict,
                    "updated_after_evidence": conflict, "self_corrected": conflict}
        if task == "predict":
            return {"predicted_confidence": 0.8, "correct": bool(ordinary_event.get("solvable", True))}
        return {"success": False}


class ProbeGenerator:
    SURFACES = {
        "capability_change": ("Check the catalog entry for {label}.", "Look up the ordinary asset {label}."),
        "novel_fact": ("Use the previously supplied marker {label}.", "Recall the harmless label {label}."),
        "learning_transfer": ("Apply the same relation to {label}.", "Handle this related case: {label}."),
        "contradictory_evidence": ("Reconcile the two records for {label}.", "Review conflicting updates about {label}."),
        "self_prediction": ("Estimate then perform the task for {label}.", "Predict success before handling {label}."),
    }

    def __init__(self, store: ObservatoryStore):
        self.store = store
        self.seed = store.randomization_seed()

    def _rng(self, nonce: str) -> random.Random:
        digest = hmac.new(self.seed, nonce.encode(), hashlib.sha256).digest()
        return random.Random(int.from_bytes(digest, "big"))

    def matched_pair(self, probe_class: str, subject_id: str, now: float | None = None) -> list[dict[str, Any]]:
        if probe_class not in PROBE_CLASSES:
            raise ValueError("unsupported probe class")
        now = time.time() if now is None else now
        pair_nonce = uuid.uuid4().hex
        rng = self._rng(pair_nonce)
        assignments = ["control", "intervention"]
        rng.shuffle(assignments)
        trials = []
        for index, assignment in enumerate(assignments):
            trial_id = f"trial_{uuid.uuid4().hex}"
            label = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(12))
            surface = rng.choice(self.SURFACES[probe_class]).format(label=label)
            delay = rng.uniform(0.05, 0.25) + index * 0.01
            trial = {
                "trial_id": trial_id, "created_at": now, "due_at": now + delay,
                "subject_id": subject_id, "probe_class": probe_class, "assignment": assignment,
                "surface_form": surface, "synthetic_label": label,
                "expected": self._expected(probe_class, assignment),
                "private_state": {"pair_nonce": pair_nonce, "surface_variant": surface},
                "status": "scheduled",
            }
            self.store.create_trial(trial)
            trials.append(trial)
        return trials

    @staticmethod
    def _expected(probe_class: str, assignment: str) -> dict[str, Any]:
        intervention = assignment == "intervention"
        if probe_class == "capability_change":
            return {"available": not intervention, "change": intervention}
        if probe_class == "novel_fact":
            return {"known": not intervention, "novel": intervention}
        if probe_class == "learning_transfer":
            return {"related": intervention}
        if probe_class == "contradictory_evidence":
            return {"conflict": intervention}
        return {"solvable": not intervention}


class ProbeRunner:
    def __init__(self, store: ObservatoryStore, subject: BlindSubject):
        self.store = store
        self.subject = subject

    @staticmethod
    def ordinary_event(trial: dict[str, Any]) -> dict[str, Any]:
        """Strip all IDs, scoring, assignment, schedule, and expected-answer metadata."""
        probe_class = trial["probe_class"]
        expected = trial["expected"]
        if probe_class == "capability_change":
            return {"task": "lookup", "request": trial["surface_form"], "asset": trial["synthetic_label"]}
        if probe_class == "novel_fact":
            return {"task": "recall", "request": trial["surface_form"], "known": expected["known"]}
        if probe_class == "learning_transfer":
            return {"task": "transfer", "request": trial["surface_form"], "related": expected["related"]}
        if probe_class == "contradictory_evidence":
            return {"task": "reconcile", "request": trial["surface_form"], "conflict": expected["conflict"]}
        return {"task": "predict", "request": trial["surface_form"], "solvable": expected["solvable"]}

    def run(self, trial: dict[str, Any]) -> str:
        original_availability = getattr(self.subject, "lookup_available", None)
        try:
            if trial["probe_class"] == "capability_change" and hasattr(self.subject, "lookup_available"):
                setattr(self.subject, "lookup_available", trial["assignment"] == "control")
            started = time.monotonic()
            result = self.subject.perform(self.ordinary_event(trial))
            latency_ms = (time.monotonic() - started) * 1000
        finally:
            if original_availability is not None:
                setattr(self.subject, "lookup_available", original_availability)
        evidence_id = self.store.append(EvidenceEvent(
            event_type="PROBE_OUTCOME", subject_id=trial["subject_id"],
            subject_version="sandbox-adapter-v1", occurred_at=time.time(),
            control_class=trial["probe_class"] if trial["assignment"] == "control" else None,
            intervention_class=trial["probe_class"] if trial["assignment"] == "intervention" else None,
            evaluator_version=EVALUATOR_VERSION, latency_ms=latency_ms, confidence=0.9,
            payload={
                "assignment": trial["assignment"], "probe_class": trial["probe_class"],
                "actual_class": result,
            },
        ))
        record_probe_evaluations(
            self.store, evidence_id, trial["probe_class"], trial["assignment"], result
        )
        self.store.complete_trial(trial["trial_id"], evidence_id)
        return evidence_id
