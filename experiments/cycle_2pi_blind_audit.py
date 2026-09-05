#!/usr/bin/env python3
"""Blind audit for the CKK CYCLE -> external 2pi question.

INTEGRITY FIREWALL
------------------
This harness is external to the CKK kernel. It MUST NOT modify, parameterize,
score, or steer grammar.py, expand.py, seeds, operators, or generation.

Stage A asks only whether a physics-blind CKK kernel independently produces
CYCLE from RECURRENCE and what structural consequences follow. It makes no
claim that CYCLE is numerically 2*pi. Any such correspondence belongs to a
separate external Stage B with frozen targets and nulls.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
GRAMMAR = GEN / "grammar.py"
EXPAND = GEN / "expand.py"
OUT = ROOT / "results" / "cycle_2pi_blind" / "stage_a_kernel.json"

# Lexical/semantic contamination checks. Deliberately avoid substring matching
# for 'pi' (which would falsely hit ordinary identifiers such as 'typing').
FORBIDDEN_PATTERNS = {
    "pi": r"(?<![A-Za-z0-9_])pi(?![A-Za-z0-9_])",
    "2*pi": r"2\s*\*\s*pi",
    "2π": r"2\s*π",
    "gravity": r"gravit",
    "mass": r"(?<![A-Za-z])mass(?![A-Za-z])",
    "planet": r"planet",
    "orbit": r"orbit",
    "quantum": r"quantum",
    "bohr": r"bohr",
    "dirac": r"dirac",
    "hawking": r"hawking",
    "schwarzschild": r"schwarzschild",
    "flux": r"flux",
    "superfluid": r"superfluid",
    "standard model": r"standard\s+model",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_kernel_blindness() -> dict:
    text = GRAMMAR.read_text() + "\n" + EXPAND.read_text()
    hits = sorted(name for name, pattern in FORBIDDEN_PATTERNS.items()
                  if re.search(pattern, text, flags=re.IGNORECASE))
    return {"pass": not hits, "forbidden_hits": hits}


def load_modules():
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
        sys.path.pop(0)


def stage_a(levels: int = 5, cap: int = 20000) -> dict:
    blind = audit_kernel_blindness()
    if not blind["pass"]:
        raise RuntimeError(f"Kernel physics-contamination tokens: {blind['forbidden_hits']}")

    grammar, expand = load_modules()
    pool, derivations = expand.expand_structural_auditable(levels=levels, cap=cap)
    cycles = [s for s in pool.values() if s.kind == grammar.CYCLE]
    cycle_ids = {s.structural_sig() for s in cycles}
    close_events = [d for d in derivations if d.operator == "op_close"]
    downstream = [d for d in derivations if any(i in cycle_ids for i in d.inputs)]

    result = {
        "schema": "ckk.cycle-2pi-blind.stage-a.v2",
        "status": "STAGE_A_PASS" if cycles and close_events else "STAGE_A_FAIL",
        "kernel_physics_blind": blind,
        "kernel_hashes": {
            "grammar_sha256": sha256(GRAMMAR),
            "expand_sha256": sha256(EXPAND),
        },
        "run": {
            "levels": levels,
            "cap": cap,
            "structural_states": len(pool),
            "derivation_events": len(derivations),
        },
        "cycle": {
            "structural_states": len(cycles),
            "close_derivation_events": len(close_events),
            "dimensions": sorted({s.dim for s in cycles}),
            "orders": sorted({s.order for s in cycles}),
            "downstream_operator_types": sorted({d.operator for d in downstream}),
            "downstream_derivation_events": len(downstream),
        },
        "claim_boundary": (
            "CKK independently generates abstract CYCLE structure from RECURRENCE. "
            "Stage A infers no angle, pi, 2*pi, physical law, constant or target. "
            "CYCLE <-> 2*pi is exclusively an external Stage-B hypothesis."
        ),
        "next_gate": (
            "Freeze this artifact. Stage B may consume it with a separately frozen "
            "physics target manifest and null controls, but may not condition or write "
            "to the CKK kernel."
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
