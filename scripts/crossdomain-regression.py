#!/usr/bin/env python3
"""Read-only cross-domain inventory and current-core regression audit.

This is deliberately fail-closed. It never writes graph/database state and it
does not turn partial historical narratives into executable domain fixtures.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
AUDIT = ROOT / "audit"
sys.path.insert(0, str(GEN))

from grammar import (  # noqa: E402
    BINARY,
    MAXDIM,
    SEEDS,
    SEED_R,
    SEED_Rn,
    UNARY,
    op_close,
    op_dual,
    op_fiber,
    op_product,
)
from expand import derivational_confluences, expand_structural_auditable  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_hash(values) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_gate_report():
    path = ROOT / "scripts" / "crossdomain-golden-gate.py"
    spec = importlib.util.spec_from_file_location("crossdomain_golden_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_report()


def seed_record(seed):
    row = {"kind": seed.kind, "dim": seed.dim, "order": seed.order, "label": seed.label, "mult": seed.mult}
    if seed.sq is not None:
        row["sq"] = seed.sq
    if seed.anti is not None:
        row["anti"] = seed.anti
    if seed.occ is not None:
        row["occ"] = seed.occ
    return row


def core_invariants():
    names = {op.__name__ for op in UNARY + BINARY}
    x0 = op_close(SEED_R)
    x2 = op_close(SEED_Rn[0])
    cross_fiber = op_fiber(x0, x2)
    dual_x0 = op_dual(x0)
    mixed_product = op_product(x0, dual_x0)
    mixed_fiber = op_fiber(x0, dual_x0)
    return {
        "selfdual_operator_absent": {
            "status": "PASS" if "op_selfdual" not in names else "FAIL",
            "observed": "op_selfdual" in names,
            "required": False,
        },
        "dual_structural_roundtrip": {
            "status": "PASS" if op_dual(dual_x0).structural_sig() == x0.structural_sig() else "FAIL",
            "selfduality": "NOT_EVALUATED",
        },
        "fiber_order_compatibility": {
            "status": "PASS" if cross_fiber is None else "FAIL",
            "input_orders": [x0.order, x2.order],
            "observed_output": list(cross_fiber.structural_sig()) if cross_fiber else None,
            "failure": "op_fiber discards the base order" if cross_fiber else None,
        },
        "product_dual_factor_preservation": {
            "status": "PASS" if mixed_product is None else "FAIL",
            "input_dual_states": [x0.dual, dual_x0.dual],
            "observed_output": list(mixed_product.structural_sig()) if mixed_product else None,
            "failure": "op_product promotes a mixed product via max(dual) without preserving factor-level dual state" if mixed_product else None,
        },
        "fiber_dual_factor_preservation": {
            "status": "PASS" if mixed_fiber is None else "FAIL",
            "input_dual_states": [x0.dual, dual_x0.dual],
            "observed_output": list(mixed_fiber.structural_sig()) if mixed_fiber else None,
            "failure": "op_fiber collapses mixed dual state" if mixed_fiber else None,
        },
        "maxdim_disclosed": {
            "status": "PASS",
            "value": MAXDIM,
            "role": "EXPERIMENT_PARAMETER",
            "forbidden_inference": "4D spacetime discovered",
        },
    }


def current_core_metrics():
    pool, events = expand_structural_auditable()
    event_keys = {event.event_key() for event in events}
    confluences = derivational_confluences(events)
    signatures = sorted(pool)
    cross_order_fiber_events = 0
    mixed_dual_product_events = 0
    mixed_dual_fiber_events = 0
    self_transition_events = 0
    for event in events:
        if event.operator == "op_fiber" and len(event.inputs) == 2 and event.inputs[0][2] != event.inputs[1][2]:
            cross_order_fiber_events += 1
        if event.operator == "op_product" and len(event.inputs) == 2 and event.inputs[0][8] != event.inputs[1][8]:
            mixed_dual_product_events += 1
        if event.operator == "op_fiber" and len(event.inputs) == 2 and event.inputs[0][8] != event.inputs[1][8]:
            mixed_dual_fiber_events += 1
        if event.output in event.inputs:
            self_transition_events += 1
    return {
        "structural_states": len(pool),
        "derivation_events_raw": len(events),
        "derivation_events_unique": len(event_keys),
        "true_derivational_confluences": len(confluences),
        "confluence_definition": ">=2 distinct DerivationEvent.event_key values produce one structural_sig",
        "structural_signature_sha256": canonical_hash(signatures),
        "kind_counts": dict(sorted(Counter(sig[0] for sig in pool).items())),
        "dimension_counts": {str(k): v for k, v in sorted(Counter(sig[1] for sig in pool).items())},
        "dual_counts": {str(k): v for k, v in sorted(Counter(sig[8] for sig in pool).items())},
        "operator_event_counts": dict(sorted(Counter(event.operator for event in events).items())),
        "cross_order_fiber_events": cross_order_fiber_events,
        "mixed_dual_product_events": mixed_dual_product_events,
        "mixed_dual_fiber_events": mixed_dual_fiber_events,
        "self_transition_events": self_transition_events,
        "known_matches": "NOT_EVALUATED_NO_INDEPENDENT_CURRENT_CORE_CATALOG",
        "rediscovered_matches": "NOT_EVALUATED_NO_INDEPENDENT_CURRENT_CORE_HOLDOUT",
        "variants": "NOT_EVALUATED_NO_FROZEN_MATCHER_BASELINE",
        "unmatched": "NOT_EVALUATED_NO_FROZEN_MATCHER_BASELINE",
        "lost_vs_historical": "NOT_COMPARABLE_EXACTLY",
        "new_vs_historical": "NOT_COMPARABLE_EXACTLY",
        "changed_structural_signatures": "NOT_COMPARABLE_EXACTLY",
    }


def build_report():
    gate = load_gate_report()
    fixture = load_json(ROOT / "crossdomain" / "physics" / "seed.fixture.json")
    core_seeds = [seed_record(seed) for seed in SEEDS]
    exact_seed_match = fixture["seeds"] == core_seeds
    invariants = core_invariants()
    metrics = current_core_metrics()
    invariant_failures = [name for name, row in invariants.items() if row["status"] == "FAIL"]
    physics_inventory = gate["domains"]["physics"]
    physics_golden_ready = bool(
        physics_inventory["expected_structural_frozen"]
        and physics_inventory["holdouts_frozen"]
    )
    if not exact_seed_match or invariant_failures:
        physics_regression = "FAIL"
    elif not physics_golden_ready:
        physics_regression = "BLOCKED_MISSING_GOLDEN_BASELINE"
    else:
        physics_regression = "PASS"

    domains = {}
    for name, inventory in gate["domains"].items():
        if name == "physics":
            domains[name] = {
                "archive_status": inventory["archive_status"],
                "regression": physics_regression,
                "seed_fixture_matches_current_core": exact_seed_match,
                "blocking_reasons": inventory.get("blocking_reasons", []) + invariant_failures,
                "current_core_diagnostic": metrics,
            }
        else:
            domains[name] = {
                "archive_status": inventory["archive_status"],
                "regression": "BLOCKED_PARTIAL_HISTORICAL_ARTIFACT",
                "blocking_reasons": inventory.get("blocking_reasons", []),
                "current_core_diagnostic": "NOT_RUN_WITHOUT_EXECUTABLE_SEEDS",
            }

    return {
        "schema": "ckk.crossdomain-regression.v1",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "starting_commit": "5128409001c77306a8b1cb04583cbc79203e5978",
        "golden_gate": gate["result"],
        "core_invariants": invariants,
        "domains": domains,
        "new_generation": {
            "eligible": physics_regression == "PASS",
            "created": False,
            "reason": "Physics Golden Regression is not green; autonomous generation is forbidden by the sealed protocol." if physics_regression != "PASS" else "ELIGIBLE_NOT_CREATED_BY_READ_ONLY_AUDIT",
        },
        "run34": {
            "generation_id": "v6-noselfdual-563f50e328c5",
            "run_id": 34,
            "role": "SEALED_HISTORICAL_PRESENTATION_SNAPSHOT",
            "unchanged": True,
            "not_a_current_core_expected_output": True,
            "counts": {"nodes": 276, "edges": 945, "historical_graph_confluences": 196},
            "selfduality": "NOT_EVALUATED",
        },
    }


def inventory_markdown(gate):
    lines = [
        "# Cross-Domain Artifact Inventory",
        "",
        "This inventory is fail-closed. Historical narrative records are not executable fixtures.",
        "",
        "| Domain | Archive | Executable seeds | Frozen output | Hold-outs | Gate |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for name, row in gate["domains"].items():
        lines.append(f"| {name.title()} | {row['archive_status']} | {'yes' if row['executable_seed_fixture'] else 'no'} | {'yes' if row['expected_structural_frozen'] else 'no'} | {'yes' if row['holdouts_frozen'] else 'no'} | {row['gate']} |")
    lines.extend(["", f"Raw-byte fixture hash gate: **{gate['hashes']['status']}** ({gate['hashes']['checked']} files).", "", f"Overall golden gate: **{gate['result']}**."])
    return "\n".join(lines) + "\n"


def regression_markdown(report):
    physics = report["domains"]["physics"]
    metrics = physics["current_core_diagnostic"]
    lines = [
        "# CKK Cross-Domain Regression",
        "",
        f"Result: **{physics['regression']} / NO NEW GENERATION**",
        "",
        "The current core was measured without catalog-label inference. A true confluence requires at least two distinct derivation events for one `structural_sig`; binary input arity is not counted as confluence.",
        "",
        "## Domain results",
        "",
    ]
    for name, row in report["domains"].items():
        lines.append(f"- {name.title()}: **{row['regression']}** ({row['archive_status']})")
    lines.extend([
        "",
        "## Current Physics-seed diagnostic",
        "",
        f"- structural states: {metrics['structural_states']}",
        f"- raw derivation events: {metrics['derivation_events_raw']}",
        f"- unique derivation events: {metrics['derivation_events_unique']}",
        f"- true derivational confluences: {metrics['true_derivational_confluences']}",
        f"- cross-order fiber events: {metrics['cross_order_fiber_events']}",
        f"- mixed-dual product events: {metrics['mixed_dual_product_events']}",
        f"- mixed-dual fiber events: {metrics['mixed_dual_fiber_events']}",
        f"- self-transition events: {metrics['self_transition_events']}",
        "",
        "Known/rediscovered/variant/unmatched are not evaluated for this current-core diagnostic because no independent current-core catalog/hold-out baseline is frozen.",
        "",
        "## Core gates",
        "",
    ])
    for name, row in report["core_invariants"].items():
        lines.append(f"- `{name}`: **{row['status']}**")
    lines.extend([
        "",
        "`MAXDIM=4` is recorded only as an experiment parameter. It is not evidence for emergent 4D spacetime. Structural dual roundtrip is tested; self-duality remains `NOT_EVALUATED`.",
        "",
        "Run 34 remains an unchanged historical presentation snapshot and was not used to fill missing expected outputs.",
    ])
    return "\n".join(lines) + "\n"


def main():
    report = build_report()
    gate = load_gate_report()
    AUDIT.mkdir(exist_ok=True)
    outputs = {
        AUDIT / "crossdomain-inventory.json": json.dumps(gate, indent=2, ensure_ascii=False) + "\n",
        AUDIT / "crossdomain-inventory.md": inventory_markdown(gate),
        AUDIT / "crossdomain-golden-suite.json": json.dumps(gate, indent=2, ensure_ascii=False) + "\n",
        AUDIT / "crossdomain-golden-suite.md": inventory_markdown(gate),
        AUDIT / "crossdomain-regression.json": json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        AUDIT / "crossdomain-regression.md": regression_markdown(report),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
