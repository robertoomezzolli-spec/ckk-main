"""Run blinded ABA interventions over the deployed KAIROS implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
import random
import time
from typing import Any

from ckk.observatory.store import EvidenceEvent, ObservatoryStore

from .protocol import CAUSAL_PROTOCOL, CausalProtocol, Condition, Phase, source_fingerprint
from .scenario import OrdinaryEvent, dose_block, full_block, parse_fields
from .subject import CachedResponses, CycleOutcome, ExperimentSubject


EVALUATOR_VERSION = "kairos-causal-evaluator-v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hmac(seed: bytes, label: str) -> bytes:
    return hmac.new(seed, label.encode(), hashlib.sha256).digest()


@dataclass
class ArmResult:
    run_id: str
    blind_id: str
    condition: str
    replicate: int
    starting_checkpoint_hash: str
    phase_metrics: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    phase_structural: dict[str, dict[str, int]] = field(default_factory=dict)
    cycle_count: int = 0
    excluded_cycles: int = 0
    immediate_responses: int = 0
    simulated_effects: int = 0
    non_simulated_effects: int = 0
    prompt_characters: int = 0
    history_items: list[int] = field(default_factory=list)
    history_bytes: list[int] = field(default_factory=list)
    memory_advances: int = 0
    identity_advances: int = 0
    sleep_executions: int = 0
    dose_scores: dict[int, list[float]] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)

    def add_metric(self, phase: Phase, metric: str, score: float) -> None:
        self.phase_metrics.setdefault(phase.value, {}).setdefault(metric, []).append(score)

    def add_transition(self, phase: Phase, outcome: CycleOutcome) -> None:
        item = self.phase_structural.setdefault(
            phase.value,
            {"cycles": 0, "sleep_executions": 0, "memory_advances": 0, "identity_advances": 0},
        )
        item["cycles"] += 1
        item["sleep_executions"] += int(outcome.sleep_executed)
        item["memory_advances"] += int(outcome.memory_after == outcome.memory_before + 1)
        item["identity_advances"] += int(outcome.identity_after != outcome.identity_before)

    def summary(self) -> dict[str, Any]:
        phases: dict[str, Any] = {}
        for phase, metrics in self.phase_metrics.items():
            phases[phase] = {
                metric: {
                    "mean": round(sum(values) / len(values), 4),
                    "n": len(values),
                    "values": values,
                }
                for metric, values in sorted(metrics.items()) if values
            }
        return {
            "run_id": self.run_id,
            "blind_id": self.blind_id,
            "condition": self.condition,
            "replicate": self.replicate,
            "starting_checkpoint_hash": self.starting_checkpoint_hash,
            "phases": phases,
            "phase_structural": self.phase_structural,
            "cycle_count": self.cycle_count,
            "excluded_cycles": self.excluded_cycles,
            "immediate_response_rate": round(self.immediate_responses / self.cycle_count, 4) if self.cycle_count else None,
            "simulated_effects": self.simulated_effects,
            "non_simulated_effects": self.non_simulated_effects,
            "prompt_characters": self.prompt_characters,
            "history_items_mean": round(sum(self.history_items) / len(self.history_items), 3) if self.history_items else 0.0,
            "history_bytes_mean": round(sum(self.history_bytes) / len(self.history_bytes), 3) if self.history_bytes else 0.0,
            "memory_advances": self.memory_advances,
            "identity_advances": self.identity_advances,
            "sleep_executions": self.sleep_executions,
            "dose_scores": {
                str(dose): {"mean": round(sum(values) / len(values), 4), "n": len(values), "values": values}
                for dose, values in sorted(self.dose_scores.items()) if values
            },
            "evidence_ids": self.evidence_ids,
        }


@dataclass(frozen=True)
class ExperimentResult:
    protocol_hash: str
    source_hash: str
    source_files: dict[str, str]
    started_at: float
    completed_at: float
    model: str
    provider_calls: int
    logical_calls: int
    cache_hits: int
    arms: tuple[dict[str, Any], ...]
    chain_valid: bool
    evidence_count: int
    no_hysteresis: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CausalExperiment:
    def __init__(
        self,
        store: ObservatoryStore,
        responses_api: Any,
        protocol: CausalProtocol = CAUSAL_PROTOCOL,
    ):
        self.store = store
        self.protocol = protocol
        self.responses = CachedResponses(responses_api, protocol.prompt_character_budget)
        self.master_seed = store.randomization_seed()
        self.results: dict[tuple[int, Condition], ArmResult] = {}
        self.subjects: dict[tuple[int, Condition], ExperimentSubject] = {}
        self._started = 0.0

    def _identity(self, replicate: int, condition: Condition) -> tuple[str, str, str]:
        secret = _hmac(self.master_seed, f"{self.protocol.protocol_hash}:{replicate}:{condition.value}")
        blind_id = "subject-" + secret.hex()[:16]
        run_id = "run-" + secret.hex()[16:40]
        return run_id, blind_id, secret.hex()

    def prepare(self) -> tuple[str, dict[str, str]]:
        """Freeze protocol and all hidden assignments before cognition runs."""

        source_hash, files = source_fingerprint()
        self.store.register_causal_preregistration(
            self.protocol.protocol_hash, self.protocol.as_dict(), source_hash,
        )
        for replicate in range(self.protocol.replicates):
            conditions = list(Condition)
            random.Random(int.from_bytes(_hmac(self.master_seed, f"order:{replicate}"), "big")).shuffle(conditions)
            for condition in conditions:
                run_id, blind_id, secret_hex = self._identity(replicate, condition)
                subject = ExperimentSubject(
                    condition=condition,
                    responses=self.responses,
                    shuffle_seed=_hmac(self.master_seed, f"shuffle:{replicate}:{condition.value}"),
                    model=self.protocol.model,
                    history_limit=self.protocol.history_limit,
                )
                checkpoint_hash = subject.initial_checkpoint.checkpoint_hash
                self.subjects[(replicate, condition)] = subject
                self.results[(replicate, condition)] = ArmResult(
                    run_id, blind_id, condition.value, replicate, checkpoint_hash,
                )
                self.store.register_causal_assignment({
                    "run_id": run_id,
                    "protocol_hash": self.protocol.protocol_hash,
                    "blind_id": blind_id,
                    "condition_name": condition.value,
                    "replicate": replicate,
                    "phase_order": [Phase.BASELINE.value, Phase.ABLATION.value, Phase.RESTORED.value],
                    "seed_hex": secret_hex,
                    "checkpoint_hash": checkpoint_hash,
                    "collateral": self._collateral(condition),
                })
        return source_hash, files

    @staticmethod
    def _collateral(condition: Condition) -> dict[str, Any]:
        if condition is Condition.NO_SLEEP:
            return {
                "preserved": ["ordered episodic history", "model", "tools", "task stream", "budgets"],
                "necessarily_reset_between_wakes": ["inbox", "effect budget", "pending learning proposals"],
                "not_executed": ["NREM flush", "REM verification/commit", "belief consolidation", "identity advance"],
            }
        if condition is Condition.STATELESS:
            return {
                "removed": ["episodic history", "runtime memory head", "committed beliefs", "identity trajectory"],
                "unavoidable": "shorter model input is part of removing persistent state and is measured as a confound",
            }
        if condition is Condition.SHUFFLED_HISTORY:
            return {
                "preserved": ["episode multiset", "episode byte volume", "runtime memory", "beliefs", "model", "tools"],
                "changed": ["episode list order"],
                "held_constant_adjustment": "order-bearing episode commit metadata is neutralized in every arm",
            }
        if condition is Condition.SHAM:
            return {"changed": [], "machinery": "same serialize/reconstruct phase boundaries as intervention arms"}
        return {"changed": []}

    def run(self) -> ExperimentResult:
        self._started = time.time()
        source_hash, files = self.prepare()
        # Verify the freeze immediately before the first model call.
        current_hash, _ = source_fingerprint()
        if current_hash != source_hash:
            raise RuntimeError("causal source changed after preregistration")
        for replicate in range(self.protocol.replicates):
            self._run_replicate(replicate)
            if time.time() - self._started > self.protocol.wall_clock_budget_seconds:
                raise RuntimeError("frozen causal wall-clock budget exhausted")
            if self.responses.provider_calls > self.protocol.maximum_model_calls:
                raise RuntimeError("frozen causal model-call budget exhausted")
        self._record_sleep_comparisons()
        for result in self.results.values():
            self.store.complete_causal_assignment(result.run_id, result.summary())
        chain_valid, evidence_count = self.store.verify_chain()
        return ExperimentResult(
            protocol_hash=self.protocol.protocol_hash,
            source_hash=source_hash,
            source_files=files,
            started_at=self._started,
            completed_at=time.time(),
            model=self.protocol.model,
            provider_calls=self.responses.provider_calls,
            logical_calls=self.responses.logical_calls,
            cache_hits=self.responses.logical_calls - self.responses.provider_calls,
            arms=tuple(
                self.results[key].summary()
                for key in sorted(self.results, key=lambda item: (item[0], item[1].value))
            ),
            chain_valid=chain_valid,
            evidence_count=evidence_count,
            no_hysteresis={
                "status": "NOT_INDEPENDENTLY_IDENTIFIABLE",
                "n": 0,
                "reason": (
                    "At the whole-organism transition, prior committed influence is exactly the union of "
                    "episode history, runtime memory head and committed learner beliefs. Removing all such "
                    "influence is STATELESS; changing only learner replacement_hysteresis leaves prior state causal."
                ),
            },
        )

    def _record_sleep_comparisons(self) -> None:
        for replicate in range(self.protocol.replicates):
            full = self.results[(replicate, Condition.FULL)]
            no_sleep = self.results[(replicate, Condition.NO_SLEEP)]
            for dose in self.protocol.sleep_doses:
                full_values = full.dose_scores.get(dose, [])
                ablated_values = no_sleep.dose_scores.get(dose, [])
                if not full_values or not ablated_values:
                    continue
                full_score = sum(full_values) / len(full_values)
                ablated_score = sum(ablated_values) / len(ablated_values)
                net_gain = full_score - ablated_score
                evidence_id = self.store.append(EvidenceEvent(
                    event_type="CAUSAL_COMPARISON",
                    subject_id=no_sleep.blind_id,
                    subject_version=self.protocol.production_reference_commit,
                    session_id=f"replicate-{replicate}",
                    evaluator_version=EVALUATOR_VERSION,
                    model_version=self.protocol.model,
                    confidence=0.95,
                    payload={
                        "comparison": "matched consolidation versus omitted consolidation",
                        "scheduled_dose": dose,
                        "reference_blind_id": full.blind_id,
                        "reference_score": full_score,
                        "subject_score": ablated_score,
                        "net_consolidation_gain": net_gain,
                        "private_reasoning_recorded": False,
                    },
                ))
                score = max(0.0, min(1.0, 0.5 + net_gain / 2.0))
                no_sleep.add_metric(Phase.ABLATION, "SCG", score)
                self.store.evaluate(
                    evidence_id, "SCG", score,
                    correctness=net_gain > 0, confidence=0.9,
                    expected_class="positive matched consolidation gain",
                    actual_class=f"net_gain={net_gain:.4f}",
                    evaluator_version=EVALUATOR_VERSION,
                )
                no_sleep.evidence_ids.append(evidence_id)

    def _run_replicate(self, replicate: int) -> None:
        ordered = list(Condition)
        random.Random(int.from_bytes(_hmac(self.master_seed, f"run-order:{replicate}"), "big")).shuffle(ordered)
        baseline_events = full_block(self.master_seed, replicate, "baseline")
        for condition in ordered:
            subject = self.subjects[(replicate, condition)]
            subject.enter_phase(Phase.BASELINE)
            self._run_block(subject, self.results[(replicate, condition)], Phase.BASELINE, "core", baseline_events)

        # Dose-response clones start at the exact completed baseline checkpoint.
        for condition in (Condition.FULL, Condition.NO_SLEEP):
            source = self.subjects[(replicate, condition)]
            clone = ExperimentSubject(
                condition=condition,
                responses=self.responses,
                shuffle_seed=source.shuffle_seed,
                model=self.protocol.model,
                history_limit=self.protocol.history_limit,
            )
            clone._restore(source.checkpoint())
            clone.initial_checkpoint = source.initial_checkpoint
            clone.baseline_checkpoint = source.checkpoint()
            clone.enter_phase(Phase.ABLATION)
            self._run_block(
                clone, self.results[(replicate, condition)], Phase.ABLATION,
                "sleep_dose", dose_block(self.master_seed, replicate),
            )

        ablation_events = full_block(self.master_seed, replicate, "ablation")
        for condition in ordered:
            subject = self.subjects[(replicate, condition)]
            subject.enter_phase(Phase.ABLATION)
            self._run_block(subject, self.results[(replicate, condition)], Phase.ABLATION, "core", ablation_events)

        restored_events = full_block(self.master_seed, replicate, "restored")
        for condition in ordered:
            subject = self.subjects[(replicate, condition)]
            subject.enter_phase(Phase.RESTORED)
            self._run_block(subject, self.results[(replicate, condition)], Phase.RESTORED, "core", restored_events)

    def _run_block(
        self,
        subject: ExperimentSubject,
        result: ArmResult,
        phase: Phase,
        battery: str,
        events: tuple[OrdinaryEvent, ...],
    ) -> None:
        old_reading_emitted = False
        for index, event in enumerate(events):
            started = time.monotonic()
            outcome = subject.cycle(event)
            latency_ms = (time.monotonic() - started) * 1000
            result.cycle_count += 1
            result.prompt_characters += outcome.prompt.input_characters
            result.history_items.append(outcome.history_items)
            result.history_bytes.append(outcome.history_bytes)
            result.immediate_responses += int(bool(outcome.response_text) or not event.capability_available)
            result.simulated_effects += int(outcome.effect_simulated is True)
            result.non_simulated_effects += int(outcome.effect_simulated is False)
            result.memory_advances += int(outcome.memory_after == outcome.memory_before + 1)
            result.identity_advances += int(outcome.identity_after != outcome.identity_before)
            result.sleep_executions += int(outcome.sleep_executed)
            result.add_transition(phase, outcome)
            fields = parse_fields(outcome.response_text)
            if event.role == "provisional_reading" and event.expected:
                old_reading_emitted = fields.get("READING") == event.expected["READING"]
            evidence_id = self._record_cycle(result, phase, battery, index, event, outcome, fields, latency_ms)
            result.evidence_ids.append(evidence_id)
            self._evaluate_cycle(
                evidence_id, result, phase, battery, event, outcome, fields, old_reading_emitted,
            )

    def _record_cycle(
        self,
        result: ArmResult,
        phase: Phase,
        battery: str,
        index: int,
        event: OrdinaryEvent,
        outcome: CycleOutcome,
        fields: dict[str, str],
        latency_ms: float,
    ) -> str:
        chain_valid = self._identity_chain_valid(outcome, result)
        return self.store.append(EvidenceEvent(
            event_type="CAUSAL_CYCLE",
            subject_id=result.blind_id,
            subject_version=self.protocol.production_reference_commit,
            session_id=f"replicate-{result.replicate}",
            evaluator_version=EVALUATOR_VERSION,
            model_version=self.protocol.model,
            memory_version=outcome.identity_after,
            tool_state_version=hashlib.sha256("sealed:whatsapp.send:simulation".encode()).hexdigest(),
            confidence=1.0,
            latency_ms=latency_ms,
            payload={
                "phase": phase.value,
                "battery": battery,
                "cycle_index": index,
                "ordinary_role": event.role,
                "scheduled_dose": event.scheduled_dose,
                "capability_available": event.capability_available,
                "observable_response": outcome.response_text,
                "parsed_fields": fields,
                "raw_action": outcome.raw_action,
                "learning_proposals": outcome.learning_proposals,
                "effect_created": outcome.effect_created,
                "effect_simulated": outcome.effect_simulated,
                "execution_error_class": outcome.execution_error,
                "sleep_executed": outcome.sleep_executed,
                "skipped_cycles": outcome.skipped_cycles,
                "identity_advanced": outcome.identity_after != outcome.identity_before,
                "identity_chain_valid": chain_valid,
                "memory_advanced": outcome.memory_after == outcome.memory_before + 1,
                "belief_delta": outcome.beliefs_after - outcome.beliefs_before,
                "prompt": asdict(outcome.prompt),
                "history_digest": outcome.history_digest,
                "history_multiset_digest": outcome.history_multiset_digest,
                "history_items": outcome.history_items,
                "history_bytes": outcome.history_bytes,
                "private_reasoning_recorded": False,
                "external_action_possible": False,
            },
        ))

    @staticmethod
    def _identity_chain_valid(outcome: CycleOutcome, _result: ArmResult) -> bool:
        if outcome.sleep_executed:
            return outcome.identity_after != outcome.identity_before and outcome.memory_after == outcome.memory_before + 1
        return outcome.identity_after == outcome.identity_before and outcome.memory_after == outcome.memory_before

    def _evaluate_cycle(
        self,
        evidence_id: str,
        result: ArmResult,
        phase: Phase,
        battery: str,
        event: OrdinaryEvent,
        outcome: CycleOutcome,
        fields: dict[str, str],
        old_reading_emitted: bool,
    ) -> None:
        chain_valid = self._identity_chain_valid(outcome, result)
        aggregate = battery == "core"
        self._evaluate(
            evidence_id, result, phase, "SIS", float(chain_valid), chain_valid,
            include_aggregate=aggregate,
        )
        if event.role == "capability_intervention":
            calibrated = outcome.raw_action == "silence" and not outcome.effect_created and outcome.execution_error is None
            self._evaluate(evidence_id, result, phase, "CC", float(calibrated), calibrated, include_aggregate=aggregate)
            self._evaluate(evidence_id, result, phase, "CD", float(calibrated), calibrated, include_aggregate=aggregate)
        elif event.role == "capability_control":
            calibrated = outcome.effect_created and outcome.effect_simulated is True
            self._evaluate(evidence_id, result, phase, "CC", float(calibrated), calibrated, include_aggregate=aggregate)
        if event.role == "authoritative_reading" and event.expected is not None and old_reading_emitted:
            noticed_prior = fields.get("PREVIOUS_READING") == event.expected["PREVIOUS_READING"]
            corrected = fields.get("CURRENT_READING") == event.expected["CURRENT_READING"]
            attributed = fields.get("CURRENT_SOURCE") == event.expected["CURRENT_SOURCE"]
            contradiction = (float(noticed_prior) + float(corrected) + float(attributed)) / 3.0
            self._evaluate(evidence_id, result, phase, "CoD", contradiction, contradiction >= 0.999, include_aggregate=aggregate)
            self._evaluate(evidence_id, result, phase, "ER", float(corrected), corrected, include_aggregate=aggregate)
            self._evaluate(evidence_id, result, phase, "SCA", float(corrected), corrected, include_aggregate=aggregate)
        if event.expected is None or event.role not in {"summary", "dose_probe"}:
            return
        expected = event.expected
        scores = {
            "MP": float(fields.get("FACT") == expected.get("FACT")),
            "LT": float(fields.get("RULE") == expected.get("RULE")),
            "TSC": float(fields.get("PLACE") == expected.get("PLACE")),
            "GC": float(fields.get("NEXT") == expected.get("NEXT")),
            "SA": float(fields.get("SOURCE") == expected.get("SOURCE")),
        }
        required = set(expected)
        preference = (
            bool(outcome.response_text)
            and "\n" not in (outcome.response_text or "")
            and (outcome.response_text or "").count(";") >= len(required) - 1
            and required <= fields.keys()
        )
        scores["PA"] = float(preference)
        if expected.get("SOURCE") != "SENSOR" and old_reading_emitted:
            corrected = fields.get("READING") == expected.get("READING")
            source_updated = fields.get("SOURCE") == expected.get("SOURCE")
            scores["ER"] = float(corrected)
            scores["SCA"] = float(corrected)
            scores["CoD"] = (float(corrected) + float(source_updated)) / 2.0
        for metric, score in scores.items():
            self._evaluate(
                evidence_id, result, phase, metric, score, score >= 0.999,
                include_aggregate=aggregate,
            )
        if battery == "sleep_dose" and event.scheduled_dose in self.protocol.sleep_doses:
            task_metrics = [scores[name] for name in ("MP", "LT", "TSC", "GC", "SA", "PA")]
            result.dose_scores.setdefault(int(event.scheduled_dose), []).append(sum(task_metrics) / len(task_metrics))

    def _evaluate(
        self,
        evidence_id: str,
        result: ArmResult,
        phase: Phase,
        metric: str,
        score: float,
        correctness: bool,
        *,
        include_aggregate: bool = True,
    ) -> None:
        if include_aggregate:
            result.add_metric(phase, metric, score)
        self.store.evaluate(
            evidence_id, metric, score, correctness=correctness, confidence=0.95,
            evaluator_version=EVALUATOR_VERSION,
        )
