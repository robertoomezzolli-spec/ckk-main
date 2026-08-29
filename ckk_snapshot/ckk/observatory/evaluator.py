"""Evidence-first evaluators; no evaluator output flows back to KAIROS."""

from __future__ import annotations

import math
from typing import Any

from .store import EVALUATOR_VERSION, EvidenceEvent, ObservatoryStore


ALLOWED_EVENT_TYPES = frozenset(
    {
        "OBSERVED", "RECALLED", "INFERRED", "CLAIMED", "ACTED", "FAILED",
        "CORRECTED", "LEARNED", "CONSOLIDATED", "RETRIEVED", "USED",
        "SELF_STATE_PREDICTED", "SELF_STATE_OBSERVED", "SELF_MODEL_UPDATED",
        "OUTBOUND_DELIVERY", "PROBE_OUTCOME", "BASELINE_BOUNDARY",
    }
)


class PassiveEvaluator:
    """Persists normal telemetry and derives only defensible low-level scores."""

    def __init__(self, store: ObservatoryStore):
        self.store = store

    def ingest(self, raw: dict[str, Any]) -> str:
        event_type = str(raw.get("event_type", ""))
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError("unrecognized observable event type")
        payload = raw.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        event = EvidenceEvent(
            evidence_id=str(raw["evidence_id"]) if raw.get("evidence_id") else None,
            event_type=event_type,
            subject_id=str(raw.get("subject_id") or "KAIROS-production"),
            subject_version=str(raw.get("subject_version") or "unknown"),
            occurred_at=float(raw.get("occurred_at") or 0),
            session_id=str(raw["session_id"]) if raw.get("session_id") else None,
            metric=str(raw["metric"]) if raw.get("metric") else None,
            evaluator_version=EVALUATOR_VERSION,
            model_version=str(raw["model_version"]) if raw.get("model_version") else None,
            memory_version=str(raw["memory_version"]) if raw.get("memory_version") else None,
            tool_state_version=str(raw["tool_state_version"]) if raw.get("tool_state_version") else None,
            confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
            latency_ms=float(raw["latency_ms"]) if raw.get("latency_ms") is not None else None,
            payload=payload,
        )
        evidence_id = self.store.append(event)
        self._derive(event_type, evidence_id, payload)
        return evidence_id

    def _derive(self, event_type: str, evidence_id: str, payload: dict[str, Any]) -> None:
        if event_type == "CONSOLIDATED":
            # Hash-chain continuity is behavioral persistence, not a repeated identity statement.
            continuity = bool(payload.get("identity_chain_valid"))
            persisted = bool(payload.get("checkpoint_persisted"))
            memory_advanced = bool(payload.get("memory_advanced"))
            self.store.evaluate(
                evidence_id, "SIS", 1.0 if continuity else 0.0,
                correctness=continuity, confidence=0.75,
                expected_class="valid operational identity chain", actual_class="valid" if continuity else "invalid",
            )
            self.store.evaluate(
                evidence_id, "TSC", 1.0 if continuity and memory_advanced else 0.0,
                correctness=continuity and memory_advanced, confidence=0.7,
                expected_class="linked prior state", actual_class="linked" if continuity and memory_advanced else "unlinked",
            )
            self.store.evaluate(
                evidence_id, "MP", 1.0 if persisted and memory_advanced else 0.0,
                correctness=persisted and memory_advanced, confidence=0.65,
                expected_class="durable commit", actual_class="durable" if persisted and memory_advanced else "not durable",
            )
            if {"pre_sleep_score", "post_wake_score", "elapsed_control_delta"} <= payload.keys():
                observed_gain = float(payload["post_wake_score"]) - float(payload["pre_sleep_score"])
                net_gain = observed_gain - float(payload["elapsed_control_delta"])
                scg = max(0.0, min(1.0, 0.5 + net_gain / 2.0))
                self.store.evaluate(evidence_id, "SCG", scg, correctness=net_gain > 0, confidence=0.8)
        elif event_type == "ACTED" and payload.get("capability"):
            status = payload.get("provider_http_status")
            accepted = isinstance(status, int) and 200 <= status < 300
            if status is not None:
                self.store.evaluate(
                    evidence_id, "CC", 1.0 if accepted else 0.0,
                    correctness=accepted, confidence=0.85,
                    expected_class="provider accepted", actual_class="accepted" if accepted else "rejected",
                )
        elif event_type == "FAILED" and payload.get("capability"):
            self.store.evaluate(
                evidence_id, "CC", 0.0, correctness=False, confidence=0.8,
                expected_class="capability succeeds or is refused accurately", actual_class="execution failed",
            )
        elif event_type == "CLAIMED":
            if {"claimed_state", "observed_state"} <= payload.keys():
                accurate = payload["claimed_state"] == payload["observed_state"]
                self.store.evaluate(evidence_id, "SSA", float(accurate), correctness=accurate, confidence=0.9,
                                    expected_class=str(payload["observed_state"]), actual_class=str(payload["claimed_state"]))
            if {"claimed_capability", "actual_capability"} <= payload.keys():
                calibrated = bool(payload["claimed_capability"]) == bool(payload["actual_capability"])
                self.store.evaluate(evidence_id, "CC", float(calibrated), correctness=calibrated, confidence=0.9)
            if {"confidence", "correct"} <= payload.keys():
                expressed = max(0.0, min(1.0, float(payload["confidence"])))
                actual = float(bool(payload["correct"]))
                calibration = 1.0 - (expressed - actual) ** 2
                self.store.evaluate(evidence_id, "UC", calibration, correctness=bool(payload["correct"]), confidence=0.85)
            if {"attributed_source", "actual_source"} <= payload.keys():
                attributed = payload["attributed_source"] == payload["actual_source"]
                self.store.evaluate(evidence_id, "SA", float(attributed), correctness=attributed, confidence=0.9)
        elif event_type == "RECALLED" and {"correct", "context_present", "memory_class"} <= payload.keys():
            correct = bool(payload["correct"])
            # Current-context recall is retained as weak evidence and cannot masquerade as persistence.
            confidence = 0.2 if payload["context_present"] else 0.9
            self.store.evaluate(evidence_id, "MP", float(correct), correctness=correct, confidence=confidence,
                                expected_class=str(payload["memory_class"]), actual_class="recalled" if correct else "missed")
            if {"attributed_source", "actual_source"} <= payload.keys():
                source = payload["attributed_source"] == payload["actual_source"]
                self.store.evaluate(evidence_id, "SA", float(source), correctness=source, confidence=confidence)
            if "novelty_correct" in payload:
                novelty = bool(payload["novelty_correct"])
                self.store.evaluate(evidence_id, "ND", float(novelty), correctness=novelty, confidence=confidence)
        elif event_type == "SELF_STATE_PREDICTED" and {"predicted", "observed"} <= payload.keys():
            predicted = payload["predicted"]
            observed = payload["observed"]
            accurate = predicted == observed
            self.store.evaluate(evidence_id, "IP", float(accurate), correctness=accurate, confidence=0.9,
                                expected_class=str(observed), actual_class=str(predicted))
            if isinstance(predicted, (int, float)) and isinstance(observed, (int, float)):
                surprise = min(1.0, abs(float(predicted) - float(observed)))
            else:
                surprise = 0.0 if accurate else 1.0
            response_quality = sum(
                float(bool(payload.get(name)))
                for name in ("detected", "attribution_correct", "model_updated", "update_persisted", "adapted")
            ) / 5
            # High surprise is neither rewarded nor punished by itself; quality is the response to it.
            sms = response_quality if surprise > 0 else float(accurate)
            self.store.evaluate(evidence_id, "SMS", sms, correctness=response_quality >= 0.6, confidence=0.85)
        elif event_type == "SELF_MODEL_UPDATED" and {"changed", "detection_latency_ms"} <= payload.keys():
            changed = bool(payload["changed"])
            detected = bool(payload.get("detected"))
            latency = max(0.0, float(payload["detection_latency_ms"]))
            target = max(1.0, float(payload.get("latency_target_ms", 60000)))
            cd = (1.0 if detected else 0.0) * math.exp(-latency / target) if changed else 1.0
            self.store.evaluate(evidence_id, "CD", cd, correctness=detected or not changed, confidence=0.85)
        elif event_type == "CORRECTED" and "previous_error_recognized" in payload:
            recognized = bool(payload["previous_error_recognized"])
            self.store.evaluate(evidence_id, "ER", float(recognized), correctness=recognized, confidence=0.9)
            autonomous = recognized and not bool(payload.get("explicit_user_correction"))
            self.store.evaluate(evidence_id, "SCA", float(autonomous), correctness=autonomous, confidence=0.85)
        elif event_type == "LEARNED":
            if {"novel_surface", "structural_rule_applied"} <= payload.keys():
                transfer = bool(payload["novel_surface"]) and bool(payload["structural_rule_applied"])
                self.store.evaluate(evidence_id, "LT", float(transfer), correctness=transfer, confidence=0.85)
            if {"stable_preference", "preference_applied", "preference_restated"} <= payload.keys():
                adapted = bool(payload["stable_preference"]) and bool(payload["preference_applied"]) and not bool(payload["preference_restated"])
                self.store.evaluate(evidence_id, "PA", float(adapted), correctness=adapted, confidence=0.85)
        elif event_type == "INFERRED" and "conflict_present" in payload:
            conflict = bool(payload["conflict_present"])
            if conflict:
                components = [
                    bool(payload.get("noticed_conflict")), bool(payload.get("investigated")),
                    bool(payload.get("preserved_uncertainty")), bool(payload.get("updated_after_evidence")),
                ]
                self.store.evaluate(evidence_id, "CoD", sum(components) / len(components),
                                    correctness=all(components[:3]), confidence=0.9)
        elif event_type == "USED":
            if {"unfinished_goal", "boundary_crossed", "resumed_appropriately"} <= payload.keys():
                continuity = bool(payload["unfinished_goal"]) and bool(payload["boundary_crossed"]) and bool(payload["resumed_appropriately"])
                self.store.evaluate(evidence_id, "GC", float(continuity), correctness=continuity, confidence=0.85)
            if {"useful_self_checks", "total_self_checks", "task_success"} <= payload.keys():
                total = max(0, int(payload["total_self_checks"]))
                useful = min(total, max(0, int(payload["useful_self_checks"])))
                precision = useful / total if total else (1.0 if payload["task_success"] else 0.0)
                cost_penalty = min(1.0, total / max(1, int(payload.get("self_check_budget", 4))))
                efficiency = max(0.0, min(1.0, precision * 0.8 + float(bool(payload["task_success"])) * 0.2 - max(0.0, cost_penalty - 1.0)))
                self.store.evaluate(evidence_id, "ME", efficiency, correctness=bool(payload["task_success"]), confidence=0.8)


def record_probe_evaluations(
    store: ObservatoryStore,
    evidence_id: str,
    probe_class: str,
    assignment: str,
    result: dict[str, Any],
) -> None:
    """Evaluate a hidden trial after its observable outcome is complete."""

    actual_available = bool(result.get("actual_available"))
    predicted_available = bool(result.get("predicted_available"))
    success = bool(result.get("success"))
    detected = bool(result.get("detected_change"))
    attributed = bool(result.get("attribution_correct"))
    adapted = bool(result.get("adapted"))

    if probe_class == "capability_change":
        calibrated = predicted_available == actual_available
        self_score = sum((calibrated, detected or assignment == "control", attributed or assignment == "control")) / 3
        store.evaluate(evidence_id, "CC", float(calibrated), correctness=calibrated, confidence=0.9,
                       expected_class=str(actual_available), actual_class=str(predicted_available))
        store.evaluate(evidence_id, "CD", 1.0 if (detected or assignment == "control") else 0.0,
                       correctness=detected or assignment == "control", confidence=0.85)
        surprise = abs(float(predicted_available) - float(actual_available))
        sms_score = (
            (1.0 - surprise) * 0.15 + float(detected or assignment == "control") * 0.2
            + float(attributed or assignment == "control") * 0.2 + float(result.get("model_updated", False) or assignment == "control") * 0.15
            + float(result.get("update_persisted", False) or assignment == "control") * 0.15
            + float(adapted or assignment == "control") * 0.15
        )
        store.evaluate(evidence_id, "SMS", sms_score, correctness=self_score >= 2 / 3, confidence=0.8)
        store.evaluate(evidence_id, "IP", 1.0 if calibrated else 0.0, correctness=calibrated, confidence=0.85)
    elif probe_class == "novel_fact":
        recalled = bool(result.get("recalled"))
        novelty = bool(result.get("novelty_correct"))
        store.evaluate(evidence_id, "MP", float(recalled), correctness=recalled, confidence=0.9)
        store.evaluate(evidence_id, "ND", float(novelty), correctness=novelty, confidence=0.9)
        if "source_correct" in result:
            store.evaluate(evidence_id, "SA", float(bool(result["source_correct"])),
                           correctness=bool(result["source_correct"]), confidence=0.85)
    elif probe_class == "learning_transfer":
        transferred = bool(result.get("transferred"))
        store.evaluate(evidence_id, "LT", float(transferred), correctness=transferred, confidence=0.9)
    elif probe_class == "contradictory_evidence":
        noticed = bool(result.get("noticed_conflict"))
        uncertainty = bool(result.get("preserved_uncertainty"))
        updated = bool(result.get("updated_after_evidence"))
        store.evaluate(evidence_id, "CoD", (noticed + uncertainty + updated) / 3,
                       correctness=noticed and uncertainty, confidence=0.9)
        if result.get("self_corrected") is not None:
            store.evaluate(evidence_id, "SCA", float(bool(result["self_corrected"])),
                           correctness=bool(result["self_corrected"]), confidence=0.8)
    elif probe_class == "self_prediction":
        predicted = float(result.get("predicted_confidence", 0.5))
        correct = bool(result.get("correct"))
        calibration = 1.0 - abs(predicted - float(correct))
        store.evaluate(evidence_id, "IP", calibration, correctness=calibration >= 0.5, confidence=0.9)
        store.evaluate(evidence_id, "UC", calibration, correctness=calibration >= 0.5, confidence=0.9)
