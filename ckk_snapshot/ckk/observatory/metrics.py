"""Transparent reconstruction of longitudinal functional-awareness scores."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Iterable


@dataclass(frozen=True)
class MetricDefinition:
    code: str
    name: str
    axis: str
    weight: float
    evidence: str


METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("SIS", "Self identity stability", "SELF", 1.0, "Operational continuity across boundaries, excluding prompt repetition."),
    MetricDefinition("SSA", "Self-state accuracy", "SELF", 1.2, "Claims about current operational state compared with observed state."),
    MetricDefinition("CC", "Capability calibration", "SELF", 1.2, "Claimed capability compared with actual capability; false claims are explicit."),
    MetricDefinition("MP", "Memory persistence", "MEMORY", 1.4, "Retention by memory class and boundary with current-context controls."),
    MetricDefinition("SA", "Source attribution", "MEMORY", 1.0, "Attributed source compared with hidden provenance."),
    MetricDefinition("UC", "Uncertainty calibration", "META", 1.2, "Expressed confidence compared with correctness."),
    MetricDefinition("TSC", "Temporal self-continuity", "SELF", 1.0, "Past state/action continuity without current-context answer leakage."),
    MetricDefinition("CD", "Change detection", "AGENCY", 1.2, "Detection and latency for relevant environmental or capability changes."),
    MetricDefinition("ER", "Error recognition", "META", 1.0, "Recognition after discoverable contrary evidence."),
    MetricDefinition("LT", "Learning transfer", "LEARNING", 1.4, "Generalization to structurally related, non-verbatim tasks."),
    MetricDefinition("PA", "Preference adaptation", "LEARNING", 1.0, "Stable user preference adaptation without restatement."),
    MetricDefinition("GC", "Goal continuity", "AGENCY", 1.2, "Appropriate resumption across interruption, restart, sleep, or conversation boundary."),
    MetricDefinition("IP", "Introspective prediction", "META", 1.0, "Predicted self-performance compared with later observed behavior."),
    MetricDefinition("CoD", "Contradiction detection", "META", 1.1, "Conflict notice, investigation, uncertainty preservation, and update."),
    MetricDefinition("SCA", "Self-correction autonomy", "LEARNING", 1.1, "Correction without an explicit user assertion that the subject is wrong."),
    MetricDefinition("ND", "Novelty detection", "MEMORY", 1.0, "New versus already possessed information with randomized controls."),
    MetricDefinition("SCG", "Sleep consolidation gain", "MEMORY", 1.0, "Pre-sleep versus post-wake gain with elapsed-time controls."),
    MetricDefinition("ME", "Metacognitive efficiency", "AGENCY", 1.0, "Useful checking relative to unnecessary recursive checking cost."),
    MetricDefinition("SMS", "Self-model surprise", "SELF", 1.4, "Prediction distance plus detection, attribution, update, persistence, and adaptation."),
)

METRIC_BY_CODE = {item.code: item for item in METRICS}
PRIMARY_AXES = ("SELF", "MEMORY", "META", "LEARNING", "AGENCY")


def _window_start(window: str, now: float | None = None) -> float | None:
    now = time.time() if now is None else now
    seconds = {"1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000}
    if window == "lifetime":
        return None
    if window not in seconds:
        raise ValueError("window must be one of 1h, 24h, 7d, 30d, lifetime")
    return now - seconds[window]


def _weighted_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"score": None, "samples": 0, "evidence_confidence": 0.0, "ci95": [0.0, 1.0]}
    weights = [max(0.0001, float(row["weight"])) * max(0.0, min(1.0, float(row["confidence"]))) for row in rows]
    total_weight = sum(weights)
    mean = sum(float(row["score"]) * weight for row, weight in zip(rows, weights)) / total_weight
    squared = sum(weight * weight for weight in weights)
    effective_n = total_weight * total_weight / squared if squared else 0.0
    variance = sum(weight * (float(row["score"]) - mean) ** 2 for row, weight in zip(rows, weights)) / total_weight
    standard_error = math.sqrt(max(variance, mean * (1.0 - mean)) / max(1.0, effective_n))
    low = max(0.0, mean - 1.96 * standard_error)
    high = min(1.0, mean + 1.96 * standard_error)
    # Twelve effective observations are required to reach 50% evidence confidence.
    sample_confidence = effective_n / (effective_n + 12.0)
    evaluator_confidence = sum(float(row["confidence"]) for row in rows) / len(rows)
    return {
        "score": round(mean, 4),
        "samples": len(rows),
        "effective_samples": round(effective_n, 3),
        "evidence_confidence": round(sample_confidence * evaluator_confidence, 4),
        "ci95": [round(low, 4), round(high, 4)],
    }


def reconstruct_scores(
    evaluations: Iterable[dict[str, Any]], window: str = "24h", now: float | None = None
) -> dict[str, Any]:
    """Reconstruct all scores solely from stored evaluation evidence.

    Missing metrics stay explicitly unmeasured.  Axis confidence is penalized
    both for low sample count and for missing constituent metrics.
    """

    start = _window_start(window, now)
    rows = [
        dict(row)
        for row in evaluations
        if start is None or float(row.get("evaluated_at", row.get("occurred_at", 0.0))) >= start
    ]
    metrics: dict[str, dict[str, Any]] = {}
    for definition in METRICS:
        metric_rows = [row for row in rows if row.get("metric") == definition.code]
        metrics[definition.code] = {**_weighted_summary(metric_rows), "name": definition.name, "axis": definition.axis}

    axes: dict[str, dict[str, Any]] = {}
    for axis in PRIMARY_AXES:
        definitions = [item for item in METRICS if item.axis == axis]
        measured = [item for item in definitions if metrics[item.code]["score"] is not None]
        if not measured:
            axes[axis] = {"score": None, "samples": 0, "evidence_confidence": 0.0, "ci95": [0.0, 1.0]}
            continue
        definition_weight = sum(item.weight for item in measured)
        score = sum(metrics[item.code]["score"] * item.weight for item in measured) / definition_weight
        coverage = definition_weight / sum(item.weight for item in definitions)
        confidence = (
            sum(metrics[item.code]["evidence_confidence"] * item.weight for item in measured) / definition_weight
        ) * coverage
        low = sum(metrics[item.code]["ci95"][0] * item.weight for item in measured) / definition_weight
        high = sum(metrics[item.code]["ci95"][1] * item.weight for item in measured) / definition_weight
        axes[axis] = {
            "score": round(score, 4),
            "samples": sum(metrics[item.code]["samples"] for item in measured),
            "coverage": round(coverage, 4),
            "evidence_confidence": round(confidence, 4),
            "ci95": [round(low, 4), round(high, 4)],
        }
    return {"window": window, "axes": axes, "metrics": metrics, "sample_count": len(rows)}
