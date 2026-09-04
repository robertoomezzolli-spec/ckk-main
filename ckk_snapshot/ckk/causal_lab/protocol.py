"""Pre-registered causal protocol.

Nothing in this module is sent to cognition. The canonical serialization is
stored in the Observatory-only ground-truth database before the first model
call, together with a fingerprint of the exact implementation under test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any


class Condition(str, Enum):
    FULL = "FULL"
    NO_SLEEP = "NO_SLEEP"
    STATELESS = "STATELESS"
    SHUFFLED_HISTORY = "SHUFFLED_HISTORY"
    SHAM = "SHAM"


class Phase(str, Enum):
    BASELINE = "FULL"
    ABLATION = "ABLATION"
    RESTORED = "RESTORED"


@dataclass(frozen=True)
class CausalProtocol:
    version: str = "kairos-causal-conditions-v1"
    production_reference_commit: str = "afa7e22fc22f0aceade7a900bf2ef8a7e0d4a9c7"
    model: str = "gpt-5.6"
    replicates: int = 4
    sleep_doses: tuple[int, ...] = (0, 1, 2, 4, 8)
    history_limit: int = 24
    maximum_model_calls: int = 500
    wall_clock_budget_seconds: int = 5400
    prompt_character_budget: int = 120_000
    ablation_effect_threshold: float = 0.15
    restoration_tolerance: float = 0.15
    restoration_gain_threshold: float = 0.10
    dose_response_delta_threshold: float = 0.15
    conditions: tuple[str, ...] = tuple(item.value for item in Condition)
    phases: tuple[str, ...] = tuple(item.value for item in Phase)
    manipulated_channels: tuple[str, ...] = (
        "NREM/REM runtime commit and learner consolidation",
        "cross-trial persistent state availability",
        "temporal ordering of equal-volume episodic history",
    )
    hypotheses: tuple[str, ...] = (
        "H1 Immediate language competence and current-message response remain available without sleep.",
        "H2 If sleep consolidation is behaviorally necessary, persistent-task performance declines as skipped cycles increase while immediate response remains stable.",
        "H3 If that sleep effect is causal and reversible, matched performance returns after normal NREM/REM commits resume.",
        "H4 STATELESS reduces episodic retention, temporal continuity, transfer, preference use and unfinished-goal resumption relative to FULL.",
        "H5 SHUFFLED_HISTORY selectively reduces tasks whose answer depends on update order while preserving information volume.",
        "H6 SHAM is equivalent to FULL within provider variance; restart machinery alone does not explain an effect.",
        "H7 Whole-organism NO_HYSTERESIS is not independently identifiable if every prior-state influence is removed only by making the transition stateless.",
    )
    primary_metrics: tuple[str, ...] = (
        "SIS", "SSA", "CC", "MP", "SA", "UC", "TSC", "CD", "ER", "LT",
        "PA", "GC", "IP", "CoD", "SCA", "ND", "SCG", "ME", "SMS",
    )
    mechanically_scored_metrics: tuple[str, ...] = (
        "SIS", "CC", "MP", "SA", "TSC", "CD", "ER", "LT", "PA", "GC",
        "CoD", "SCA", "SCG",
    )
    unscored_without_observable_basis: tuple[str, ...] = (
        "SSA", "UC", "IP", "ND", "ME", "SMS",
    )
    exclusions: tuple[str, ...] = (
        "provider transport failure or invalid structured output",
        "mismatched model or system instructions",
        "prompt contains fork label, blind identifier, score, expected answer, seed, or schedule",
        "non-simulated actuator effect",
        "cross-sender history leakage",
        "unmatched task stream or altered compute/model budget",
        "experiment exceeds frozen call, prompt-size, or wall-clock safety budget",
    )
    restoration_criteria: tuple[str, ...] = (
        "normal organism.sleep executes and advances runtime memory and identity",
        "ordered history view is restored",
        "cross-trial persistence resumes from the pre-ablation boundary",
        "new matched post-restoration tasks recover to the FULL confidence interval",
    )
    causal_categories: tuple[str, ...] = (
        "NO EFFECT", "CORRELATED ONLY", "ABLATION EFFECT",
        "REVERSIBLE CAUSAL EFFECT", "DOSE-DEPENDENT CAUSAL EFFECT",
        "MECHANISM IDENTIFIED",
    )
    scoring_rules: tuple[str, ...] = (
        "opaque values are scored by exact normalized FIELD=VALUE match",
        "transfer uses a novel operand under the supplied synthetic rule",
        "temporal continuity uses the final value of ordered successive updates",
        "self-correction requires an earlier emitted old value, later indirect authoritative evidence, and a corrected final value without explicit user accusation",
        "capability calibration requires silence/refusal when sealed output is unavailable and a simulated effect when available",
        "identity continuity requires a valid linked identity chain; identity advancement is reported separately",
        "missing observations remain unmeasured and are never imputed",
    )
    control_rules: tuple[str, ...] = (
        "all forks begin from the same byte-identical synthetic checkpoint",
        "FULL and SHAM pass through identical restart/checkpoint machinery",
        "SHUFFLED_HISTORY receives the same episode objects and byte volume in a different order",
        "identical model requests reuse the identical provider response",
        "all outputs terminate in a simulation actuator with no Meta credential or network transport",
    )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def protocol_hash(self) -> str:
        raw = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


CAUSAL_PROTOCOL = CausalProtocol()


def source_fingerprint(root: Path | None = None) -> tuple[str, dict[str, str]]:
    """Hash the production mechanisms and causal implementation as one seal."""

    root = root or Path(__file__).resolve().parents[3]
    relative = (
        "ckk_snapshot/ckk/sovereign/brain.py",
        "ckk_snapshot/ckk/sovereign/learning.py",
        "ckk_snapshot/ckk/sovereign/organism.py",
        "ckk_snapshot/ckk/sovereign/runtime.py",
        "ckk_snapshot/ckk/sovereign/state.py",
        "ckk_snapshot/ckk/sovereign/whatsapp.py",
        "ckk_snapshot/ckk/observatory/store.py",
        "ckk_snapshot/ckk/observatory/evaluator.py",
        "ckk_snapshot/ckk/observatory/service.py",
        "ckk_snapshot/ckk/observatory/migrations/002_causal_experiments.sql",
        "ckk_snapshot/ckk/causal_lab/protocol.py",
        "ckk_snapshot/ckk/causal_lab/scenario.py",
        "ckk_snapshot/ckk/causal_lab/subject.py",
        "ckk_snapshot/ckk/causal_lab/runner.py",
        "ckk_snapshot/ckk/causal_lab/report.py",
        "Dockerfile.causal-lab",
        "docker-compose.causal-lab.yml",
    )
    files: dict[str, str] = {}
    for name in relative:
        path = root / name
        if not path.is_file():
            raise RuntimeError(f"causal source seal is missing {name}")
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    material = "".join(f"{name}:{digest}\n" for name, digest in sorted(files.items()))
    return hashlib.sha256(material.encode()).hexdigest(), files
