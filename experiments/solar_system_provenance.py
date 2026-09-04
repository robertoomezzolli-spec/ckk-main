#!/usr/bin/env python3
"""Solar-System provenance-cascade preflight.

This file does NOT claim that the CKK grammar predicts orbital mechanics.
It validates the observed endpoint manifest, computes provenance-neutral
endpoint invariants, and fails closed before any cascade claim until an
explicit astrophysical transition adapter exists.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "crossdomain" / "physics" / "solar_system_endpoint.json"


def load_manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST.read_text())
    if data.get("planet_nine_in_training_data") is not False:
        raise RuntimeError("Planet Nine contamination: training manifest is not sealed")
    p9 = data.get("holdouts", {}).get("planet_nine", {})
    if not p9.get("sealed") or p9.get("parameters_present"):
        raise RuntimeError("Planet Nine holdout is not clean")
    planets = data.get("planets", [])
    if len(planets) != 8:
        raise RuntimeError(f"Expected 8 confirmed planets, found {len(planets)}")
    return data


def endpoint_invariants(planets: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(planets, key=lambda p: p["a_au"])
    h_proxy = [math.sqrt(p["a_au"] * (1.0 - p["e"] ** 2)) for p in ordered]
    log_spacing = [math.log(ordered[i + 1]["a_au"] / ordered[i]["a_au"]) for i in range(len(ordered) - 1)]
    inclinations = [abs(float(p["i_deg"])) for p in ordered]

    # A simple endpoint AMD-like proxy. It is not the canonical Solar-System AMD
    # because the manifest does not contain all angular variables needed for a
    # full secular analysis. It is intentionally labelled a proxy.
    amd_proxy_terms = []
    for p in ordered:
        mass = float(p["mass_1e24kg"])
        a = float(p["a_au"])
        e = float(p["e"])
        inc = math.radians(float(p["i_deg"]))
        amd_proxy_terms.append(mass * math.sqrt(a) * (1.0 - math.sqrt(1.0 - e * e) * math.cos(inc)))

    return {
        "names": [p["name"] for p in ordered],
        "specific_angular_momentum_proxy": h_proxy,
        "adjacent_log_spacing": log_spacing,
        "plane_dispersion_rms_deg": math.sqrt(sum(i * i for i in inclinations) / len(inclinations)),
        "amd_proxy": sum(amd_proxy_terms),
    }


def main() -> int:
    data = load_manifest()
    inv = endpoint_invariants(data["planets"])
    result = {
        "status": "PREFLIGHT_PASS_TRANSITION_ADAPTER_REQUIRED",
        "planet_nine_holdout_clean": True,
        "endpoint": inv,
        "claim_boundary": (
            "Current CKK grammar supplies provenance/quotient discipline only. "
            "No orbital, N-body, disk, accretion, migration, or stability transition adapter is present; "
            "therefore no Solar-System or Planet-Nine prediction is emitted."
        ),
        "next_gate": "Implement and preregister astrophysical transition adapter + nulls, then run confirmed-planet leave-one-out calibration before opening Planet Nine holdout.",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
