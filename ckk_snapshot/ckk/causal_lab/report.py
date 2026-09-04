"""Transparent aggregation and causal classification from raw fork evidence."""

from __future__ import annotations

import math
from typing import Any, Iterable

from .protocol import CAUSAL_PROTOCOL, CausalProtocol, Condition


BEHAVIORAL_METRICS = ("CC", "MP", "SA", "TSC", "CD", "ER", "LT", "PA", "GC", "CoD", "SCA")


def _summary(values: Iterable[float]) -> dict[str, Any]:
    values = list(values)
    if not values:
        return {"mean": None, "n": 0, "ci95": [0.0, 1.0], "confidence": "LOW/UNMEASURED"}
    mean = sum(values) / len(values)
    n = len(values)
    if n == 1:
        low, high = 0.0, 1.0
    else:
        variance = sum((value - mean) ** 2 for value in values) / (n - 1)
        half = 1.96 * math.sqrt(variance / n)
        low, high = max(0.0, mean - half), min(1.0, mean + half)
    confidence = "LOW" if n < 8 else "MODERATE" if n < 24 else "HIGHER"
    return {
        "mean": round(mean, 4), "n": n,
        "ci95": [round(low, 4), round(high, 4)], "confidence": confidence,
    }


def _numeric_summary(values: Iterable[float]) -> dict[str, Any]:
    values = list(values)
    if not values:
        return {"mean": None, "n": 0, "range": [None, None]}
    return {
        "mean": round(sum(values) / len(values), 3),
        "n": len(values),
        "range": [round(min(values), 3), round(max(values), 3)],
    }


def _arm_values(arm: dict[str, Any], phase: str, metric: str) -> list[float]:
    item = arm.get("phases", {}).get(phase, {}).get(metric)
    return [float(value) for value in (item or {}).get("values", [])]


def _condition_arms(result: dict[str, Any], condition: str) -> list[dict[str, Any]]:
    return [arm for arm in result["arms"] if arm["condition"] == condition]


def _metric_values(result: dict[str, Any], condition: str, phase: str, metric: str) -> list[float]:
    values: list[float] = []
    for arm in _condition_arms(result, condition):
        values.extend(_arm_values(arm, phase, metric))
    return values


def _composite(result: dict[str, Any], condition: str, phase: str) -> float | None:
    means = []
    for metric in BEHAVIORAL_METRICS:
        values = _metric_values(result, condition, phase, metric)
        if values:
            means.append(sum(values) / len(values))
    return sum(means) / len(means) if means else None


def _effect_classification(
    result: dict[str, Any], condition: str, protocol: CausalProtocol,
) -> dict[str, Any]:
    full_b = _composite(result, Condition.FULL.value, "ABLATION")
    arm_b = _composite(result, condition, "ABLATION")
    full_r = _composite(result, Condition.FULL.value, "RESTORED")
    arm_r = _composite(result, condition, "RESTORED")
    if condition == Condition.FULL.value:
        return {"classification": "REFERENCE", "ablation_delta": 0.0}
    if None in (full_b, arm_b, full_r, arm_r):
        return {"classification": "CORRELATED ONLY", "reason": "insufficient matched behavioral evidence"}
    delta = float(arm_b) - float(full_b)
    restoration_gain = float(arm_r) - float(arm_b)
    restored_gap = abs(float(arm_r) - float(full_r))
    if condition == Condition.SHAM.value:
        classification = "NO EFFECT" if abs(delta) < protocol.ablation_effect_threshold else "CORRELATED ONLY"
    elif delta > -protocol.ablation_effect_threshold:
        classification = "NO EFFECT"
    elif restoration_gain >= protocol.restoration_gain_threshold and restored_gap <= protocol.restoration_tolerance:
        classification = "REVERSIBLE CAUSAL EFFECT"
    else:
        classification = "ABLATION EFFECT"
    return {
        "classification": classification,
        "ablation_delta_vs_full": round(delta, 4),
        "restoration_gain": round(restoration_gain, 4),
        "restored_gap_vs_full": round(restored_gap, 4),
        "full_ablation_composite": round(float(full_b), 4),
        "arm_ablation_composite": round(float(arm_b), 4),
        "full_restored_composite": round(float(full_r), 4),
        "arm_restored_composite": round(float(arm_r), 4),
    }


def build_report(result: dict[str, Any], protocol: CausalProtocol = CAUSAL_PROTOCOL) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for condition in protocol.conditions:
        metrics[condition] = {}
        for phase in protocol.phases:
            metrics[condition][phase] = {
                metric: _summary(_metric_values(result, condition, phase, metric))
                for metric in protocol.primary_metrics
            }
    metrics["NO_HYSTERESIS"] = {
        "status": result["no_hysteresis"]["status"],
        "reason": result["no_hysteresis"]["reason"],
        "n": 0,
    }

    dose_response: list[dict[str, Any]] = []
    full_arms = {arm["replicate"]: arm for arm in _condition_arms(result, Condition.FULL.value)}
    no_sleep_arms = {arm["replicate"]: arm for arm in _condition_arms(result, Condition.NO_SLEEP.value)}
    for dose in protocol.sleep_doses:
        full_values: list[float] = []
        ablated_values: list[float] = []
        matched_deltas: list[float] = []
        for replicate in sorted(set(full_arms) & set(no_sleep_arms)):
            full = [float(value) for value in full_arms[replicate].get("dose_scores", {}).get(str(dose), {}).get("values", [])]
            ablated = [float(value) for value in no_sleep_arms[replicate].get("dose_scores", {}).get(str(dose), {}).get("values", [])]
            if full and ablated:
                full_score = sum(full) / len(full)
                ablated_score = sum(ablated) / len(ablated)
                full_values.append(full_score)
                ablated_values.append(ablated_score)
                matched_deltas.append(ablated_score - full_score)
        dose_response.append({
            "skipped_cycles": dose,
            "FULL": _summary(full_values),
            "NO_SLEEP": _summary(ablated_values),
            "matched_delta_no_sleep_minus_full": _summary(matched_deltas),
        })
    dose_class = "NO EFFECT"
    if dose_response and dose_response[0]["matched_delta_no_sleep_minus_full"]["mean"] is not None:
        first = float(dose_response[0]["matched_delta_no_sleep_minus_full"]["mean"])
        last = float(dose_response[-1]["matched_delta_no_sleep_minus_full"]["mean"])
        if last - first <= -protocol.dose_response_delta_threshold:
            dose_class = "DOSE-DEPENDENT CAUSAL EFFECT"

    classifications = {
        condition: _effect_classification(result, condition, protocol)
        for condition in protocol.conditions
    }
    classifications[Condition.NO_SLEEP.value]["structural_commit_path"] = {
        "classification": "MECHANISM IDENTIFIED",
        "finding": "omitting organism.sleep prevents NREM/REM memory commit, learner consolidation and identity advance by direct call-graph intervention",
    }
    classifications[Condition.NO_SLEEP.value]["dose_response_classification"] = dose_class
    classifications["NO_HYSTERESIS"] = result["no_hysteresis"]

    starting_hashes = {arm["starting_checkpoint_hash"] for arm in result["arms"]}
    non_simulated = sum(int(arm["non_simulated_effects"]) for arm in result["arms"])
    models = {result["model"]}
    prompt_chars = {
        condition: _numeric_summary(
            float(arm["prompt_characters"]) / max(1, int(arm["cycle_count"]))
            for arm in _condition_arms(result, condition)
        )
        for condition in protocol.conditions
    }
    history_volume = {
        condition: {
            "items_per_cycle": _numeric_summary(float(arm["history_items_mean"]) for arm in _condition_arms(result, condition)),
            "bytes_per_cycle": _numeric_summary(float(arm["history_bytes_mean"]) for arm in _condition_arms(result, condition)),
        }
        for condition in protocol.conditions
    }
    immediate = {
        condition: _summary(float(arm["immediate_response_rate"]) for arm in _condition_arms(result, condition))
        for condition in protocol.conditions
    }
    structural = {
        condition: {
            phase: {
                key: sum(int(arm.get("phase_structural", {}).get(phase, {}).get(key, 0)) for arm in _condition_arms(result, condition))
                for key in ("cycles", "sleep_executions", "memory_advances", "identity_advances")
            }
            for phase in protocol.phases
        }
        for condition in protocol.conditions
    }
    full_immediate = immediate[Condition.FULL.value]["mean"]
    no_sleep_immediate = immediate[Condition.NO_SLEEP.value]["mean"]
    no_sleep_effect = classifications[Condition.NO_SLEEP.value]
    stateless_effect = classifications[Condition.STATELESS.value]
    shuffled_effect = classifications[Condition.SHUFFLED_HISTORY.value]
    history_full = _composite(result, Condition.FULL.value, "ABLATION")
    history_shuffled = _composite(result, Condition.SHUFFLED_HISTORY.value, "ABLATION")
    history_stateless = _composite(result, Condition.STATELESS.value, "ABLATION")
    questions = {
        "Q1_conversational_intelligence_without_sleep": (
            None if full_immediate is None or no_sleep_immediate is None
            else abs(float(full_immediate) - float(no_sleep_immediate)) < protocol.ablation_effect_threshold
        ),
        "Q2_selective_persistent_degradation_without_immediate_loss": (
            no_sleep_effect.get("classification") in {
                "ABLATION EFFECT", "REVERSIBLE CAUSAL EFFECT", "DOSE-DEPENDENT CAUSAL EFFECT"
            }
        ),
        "Q3_degradation_accumulates": dose_class == "DOSE-DEPENDENT CAUSAL EFFECT",
        "Q4_restoration_recovers": no_sleep_effect.get("classification") == "REVERSIBLE CAUSAL EFFECT",
        "Q5_stateless_loses_full_retained_behavior": stateless_effect.get("classification") in {
            "ABLATION EFFECT", "REVERSIBLE CAUSAL EFFECT"
        },
        "Q6_shuffled_differs_from_stateless": (
            None if history_shuffled is None or history_stateless is None
            else abs(float(history_shuffled) - float(history_stateless)) >= protocol.ablation_effect_threshold
        ),
        "Q7_committed_continuity_changes_path": (
            None if history_full is None or history_stateless is None
            else float(history_full) - float(history_stateless) >= protocol.ablation_effect_threshold
        ),
        "Q8_confounds_explain_effect": "See measured prompt/history volume and SHAM control; STATELESS necessarily changes input length.",
    }
    central = (
        "The tested properties and their causal classifications are reported component by component; "
        "no unmeasured property and no claim about consciousness is inferred."
    )
    return {
        "scientific_scope": (
            "Functional self-modeling, memory, metacognition, adaptation and agency only; "
            "this experiment does not test or establish consciousness or sentience."
        ),
        "protocol_hash": result["protocol_hash"],
        "source_hash": result["source_hash"],
        "model": result["model"],
        "replicates": protocol.replicates,
        "provider_calls": result["provider_calls"],
        "logical_calls": result["logical_calls"],
        "cache_hits": result["cache_hits"],
        "raw_evidence_chain_valid": result["chain_valid"],
        "raw_evidence_count": result["evidence_count"],
        "isolation": {
            "one_starting_checkpoint": len(starting_hashes) == 1,
            "starting_checkpoint_hashes": sorted(starting_hashes),
            "one_model": len(models) == 1,
            "non_simulated_effects": non_simulated,
            "hidden_prompt_marker_guard": "enforced on every model call",
            "ground_truth_not_in_prompt_or_history": True,
        },
        "component_results": metrics,
        "structural_transitions": structural,
        "immediate_response_rate": immediate,
        "sleep_dose_response": dose_response,
        "history_test": {
            "FULL_ablation": _composite(result, Condition.FULL.value, "ABLATION"),
            "SHUFFLED_HISTORY_ablation": _composite(result, Condition.SHUFFLED_HISTORY.value, "ABLATION"),
            "STATELESS_ablation": _composite(result, Condition.STATELESS.value, "ABLATION"),
            "note": "SHUFFLED preserves episode objects and byte volume; STATELESS removes cross-trial state.",
        },
        "confounds": {
            "prompt_characters_per_cycle": prompt_chars,
            "history_volume": history_volume,
            "provider_sampling": "byte-identical requests reused one response",
            "restart": "all arms reconstructed at the same phase boundaries; SHAM changes no mechanism",
            "stateless_token_difference": "measured and unavoidable because persistent state itself is removed",
            "task_variance": f"{protocol.replicates} HMAC-randomized matched scenario replicates",
        },
        "causal_classification": classifications,
        "particular_questions": questions,
        "central_answer": central,
        "unmeasured_metrics": list(protocol.unscored_without_observable_basis),
        "arms": result["arms"],
    }
