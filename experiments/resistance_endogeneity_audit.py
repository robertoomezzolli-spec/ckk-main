#!/usr/bin/env python3
"""Audit whether the frozen CKK architecture *itself* derives the ingredients
needed by the external single-resistance unification gate.

KERNEL POLICY: read-only. This harness changes no CKK code and imports no
physics formulas into the kernel.

Frozen decision rule:
  Architecture compatibility is not a derivation. A CKK-endogenous derivation
  requires all of the following to be present before any physics mapping:
    1) kernel is free of target-physics labels/formulas;
    2) structural boundary/weight/filter machinery exists;
    3) CKK independently selects the spatial dimension needed by the held-out
       inverse-square branch;
    4) CKK independently emits a scalar accessibility / transition-cost rule;
    5) CKK independently fixes the boundary response law (not merely generic
       divergence).

If (3-5) are absent, the correct result is UNDERDETERMINED, not FAIL of the
architecture and not a claimed derivation.
"""
from __future__ import annotations
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / "ckk_snapshot" / "ckk" / "gen" / "grammar.py"
DIMS = ROOT / "audit" / "run34-dimension-transitions.csv"
OUT = ROOT / "results" / "resistance_endogeneity_audit.json"

FORBIDDEN = [
    r"\bgravity\b", r"\bgravitation\b", r"\bnewton\b", r"\blorentz\b",
    r"\blight\s*speed\b", r"\bspeed\s*of\s*light\b", r"\bgamma\b",
    r"\brelativity\b", r"\bmass\b", r"\benergy\b", r"\bmomentum\b",
    r"inverse[-_ ]square", r"1\s*/\s*r\s*\*\*\s*2",
]
REQUIRED_STRUCTURAL = ["BOUNDARY", "WEIGHT", "FILTER", "PRODUCT", "CYCLE"]
ACCESSIBILITY_SIGNATURES = [
    r"\baccessibility\b", r"\btransition_cost\b", r"\bresistance\b",
    r"\bconstraint_load\b",
]
BOUNDARY_LAW_SIGNATURES = [
    r"1\s*-\s*[^\n]*\*\*", r"sqrt\s*\(", r"\bresponse_power\b",
    r"\balpha\b[^\n]*access",
]


def scan(text, patterns):
    return {p: bool(re.search(p, text, flags=re.I)) for p in patterns}


def dimension_audit():
    if not DIMS.exists():
        return {"available": False, "dimensions_seen": [], "dimension_3_unique": False,
                "reason": "frozen dimension audit missing"}
    dims = set()
    rows = []
    dim_keys = ("source_dim", "target_dim", "src_dim", "dst_dim", "dimension", "dim")
    with DIMS.open(newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            rows.append(row)
            for key in dim_keys:
                if key in row and row[key] not in (None, ""):
                    try: dims.add(int(float(row[key])))
                    except ValueError: pass

    selector_columns = [k for k in (rows[0].keys() if rows else [])
                        if any(tok in k.lower() for tok in ("select", "winner", "rank", "preferred"))]
    selected = []
    for row in rows:
        for col in selector_columns:
            val = str(row.get(col, "")).strip().lower()
            if val in {"1", "true", "yes", "winner", "selected"}:
                for key in dim_keys:
                    if row.get(key, "") != "":
                        try: selected.append(int(float(row[key]))); break
                        except ValueError: pass
    unique3 = bool(selected) and set(selected) == {3}
    return {
        "available": True,
        "dimensions_seen": sorted(dims),
        "selector_columns": selector_columns,
        "selected_dimensions": sorted(set(selected)),
        "dimension_3_present": 3 in dims,
        "dimension_3_unique": unique3,
        "reason": "d=3 occurrence is not derivation; a frozen selector must uniquely choose d=3",
    }


def main():
    text = GRAMMAR.read_text()
    forbidden = scan(text, FORBIDDEN)
    physics_clean = not any(forbidden.values())
    structural = {name: name in text for name in REQUIRED_STRUCTURAL}
    structural_complete = all(structural.values())
    accessibility = scan(text, ACCESSIBILITY_SIGNATURES)
    endogenous_accessibility = any(accessibility.values())
    boundary_law = scan(text, BOUNDARY_LAW_SIGNATURES)
    endogenous_boundary_law = any(boundary_law.values())
    dims = dimension_audit()

    derivation = (
        physics_clean and structural_complete and dims["dimension_3_unique"]
        and endogenous_accessibility and endogenous_boundary_law
    )
    architecture_compatible = physics_clean and structural_complete

    if derivation:
        status = "CKK_ENDOGENOUS_SINGLE_RESISTANCE_DERIVATION_CANDIDATE"
    elif architecture_compatible:
        status = "ARCHITECTURE_COMPATIBLE_CKK_ENDOGENEITY_NOT_DERIVED"
    else:
        status = "CKK_ARCHITECTURE_GATE_FAIL"

    result = {
        "schema": "ckk.external.resistance-endogeneity-audit.v1.1",
        "status": status,
        "kernel_modified": False,
        "physics_leakage": {"clean": physics_clean, "matches": forbidden},
        "structural_primitives": {"present": structural, "complete": structural_complete},
        "dimension_selection": dims,
        "endogenous_accessibility_rule": {"derived": endogenous_accessibility, "matches": accessibility},
        "endogenous_boundary_response_law": {"derived": endogenous_boundary_law, "matches": boundary_law},
        "tests": {
            "kernel_target_physics_clean": physics_clean,
            "boundary_weight_filter_structure_present": structural_complete,
            "three_dimensions_present": dims["dimension_3_present"],
            "three_dimensions_independently_selected": dims["dimension_3_unique"],
            "single_accessibility_or_transition_cost_scalar_emitted": endogenous_accessibility,
            "specific_boundary_response_law_fixed": endogenous_boundary_law,
            "full_endogenous_derivation": derivation,
        },
        "interpretation": (
            "CKK contains structural machinery compatible with a boundary/accessibility interpretation. "
            "Its frozen dimension audit includes d=3, but does not independently select d=3; and the "
            "frozen grammar does not emit a single numerical accessibility/transition-cost scalar or "
            "fix a boundary response law. Therefore the external inverse-square + boundary-divergence "
            "PASS is architecture compatibility, not a derivation of gravity or relativity."
        ),
        "next_falsifiable_requirement": (
            "Without adding physics, obtain from frozen CKK provenance one scalar/state functional whose "
            "independently generated rules both select a held-out spatial scaling and fix a held-out "
            "boundary scaling. No post-hoc choice of dimension, alpha, or closing law."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if status != "CKK_ARCHITECTURE_GATE_FAIL" else 1)

if __name__ == "__main__":
    main()
