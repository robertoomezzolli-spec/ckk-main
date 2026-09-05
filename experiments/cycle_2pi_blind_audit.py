#!/usr/bin/env python3
"""Blind audit for the CKK CYCLE -> external 2pi question.

INTEGRITY FIREWALL
------------------
This harness is external to the CKK kernel. It MUST NOT modify, parameterize,
score, or steer grammar.py, expand.py, seeds, operators, or generation.

Question split into two stages:
  A. Kernel-side (physics blind): does CKK independently produce CYCLE and
     downstream structural consequences from RECURRENCE?
  B. External-side (physics aware, separate evidence): do independently
     specified physical targets repeatedly require 2*pi periodic closure?

This script implements Stage A only. It deliberately contains no physical
formula matcher and emits no claim that CYCLE == 2*pi. Stage B must consume a
sealed Stage-A artifact and compare it against a separately frozen target
manifest.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
GRAMMAR = GEN / "grammar.py"
EXPAND = GEN / "expand.py"
OUT = ROOT / "results" / "cycle_2pi_blind" / "stage_a_kernel.json"

FORBIDDEN_KERNEL_TOKENS = (
    "pi", "2*pi", "2π", "gravity", "gravit", "mass", "planet", "orbit",
    "quantum", "bohr", "dirac", "hawking", "schwarzschild", "flux",
    "superfluid", "standard model",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_kernel_blindness() -> dict:
    text = (GRAMMAR.read_text() + "\n" + EXPAND.read_text()).lower()
    hits = sorted({tok for tok in FORBIDDEN_KERNEL_TOKENS if tok.lower() in text})
    return {"pass": not hits, "forbidden_hits": hits}


def load_modules():
    # expand.py imports grammar by module name; make the sealed generator dir
    # importable without copying or editing kernel files.
    import sys
    sys.path.insert(0, str(GEN))
    try:
        gs = importlib.util.spec_from_file_location("grammar", GRAMMAR)
        grammar = importlib.util.module_from_spec(gs)
        assert gs.loader
        gs.loader.exec_module(grammar)
        sys.modules["grammar"] = grammar
        es = importlib.util.spec_from_file_location("expand", EXPAND)
        expand = importlib.util.module_from_spec(es)
        assert es.loader
        es.loader.exec_module(expand)
        return grammar, expand
    finally:
        # modules stay loaded; path does not need to remain globally inserted.
        sys.path.pop(0)


def stage_a(levels: int = 5, cap: int = 20000) -> dict:
    blind = audit_kernel_blindness()
    if not blind["pass"]:
        raise RuntimeError(f"Kernel physics-contamination tokens: {blind['forbidden_hits']}")

    grammar, expand = load_modules()
    pool, derivations = expand.expand_structural_auditable(levels=levels, cap=cap)

    cycle_sig = lambda s: s.kind == grammar.CYCLE
    cycles = [s for s in pool.values() if cycle_sig(s)]
    cycle_ids = {s.structural_sig() for s in cycles}

    close_events = [d for d in derivations if d.operator == "op_close"]
    downstream = [d for d in derivations if any(i in cycle_ids for i in d.inputs)]
    downstream_ops = sorted({d.operator for d in downstream})

    # CKK-side claim is intentionally structural only.
    result = {
        "schema": "ckk.cycle-2pi-blind.stage-a.v1",
        "status": "STAGE_A_PASS" if cycles and close_events else "STAGE_A_FAIL",
        "kernel_physics_blind": blind,
        "kernel_hashes": {"grammar_sha256": sha256(GRAMMAR), "expand_sha256": sha256(EXPAND)},
        "run": {"levels": levels, "cap": cap, "structural_states": len(pool), "derivation_events": len(derivations)},
        "cycle": {
            "structural_states": len(cycles),
            "close_derivation_events": len(close_events),
            "dimensions": sorted({s.dim for s in cycles}),
            "orders": sorted({s.order for s in cycles}),
            "downstream_operator_types": downstream_ops,
            "downstream_derivation_events": len(downstream),
        },
        "claim_boundary": (
            "CKK independently generates abstract CYCLE structure from RECURRENCE. "
            "No numeric angle, pi, 2*pi, physical law, constant, or physical target "
            "is inferred by Stage A. Any CYCLE <-> 2*pi correspondence is an external "
            "Stage-B hypothesis and must be scored against frozen nulls."
        ),
        "next_gate": (
            "Freeze this artifact, then build an external target manifest with positive "
            "and negative controls. Stage B may read this artifact but may not write to "
            "or condition the CKK kernel."
        ),
    }
    return result


def main() -> int:
    result = stage_a()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "STAGE_A_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
