#!/usr/bin/env python3
"""Real-satellite evidence gate for global/orientation-odd residuals.

KERNEL POLICY: CKK kernel is read-only. This script does not import CKK.

Purpose
-------
Test the *evidence architecture*, not invent a new effect. We use a recent
real satellite experiment (LARES-2 + LAGEOS, with GRACE gravity-field input)
as an overdetermined case:

- local/background gravity field constrained independently by GRACE models;
- two laser-ranged satellites with nearly supplementary orbital planes;
- the target observable is the secular nodal residual, which contains the
  orientation-sensitive frame-dragging term;
- Nature 2026 reports agreement with GR at ~2e-3 relative uncertainty.

Predeclared interpretation:
- if the architecture is overdetermined and the measured global term agrees
  with GR, then this is a REAL_POSITIVE_CONTROL for our instrument but
  NO_NEW_LOOP_RESIDUAL_DETECTED;
- a new-state claim would require a reproducible leftover beyond the reported
  uncertainty after the same cross-satellite/background-field constraints.

This is not a raw-data reanalysis; it is a held evidence gate over published
experimental results and must be labelled as such.
"""
from __future__ import annotations
import json
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"results"/"satellite_loop_evidence_gate.json"

SOURCES={
  "nature_2026": {
    "doi":"10.1038/s41586-026-10715-0",
    "facts":{
      "uses_lares2_and_lageos":True,
      "uses_grace_gravity_models":True,
      "combined_nodal_residuals":True,
      "relative_uncertainty":2e-3,
      "reported_stringent_confirmation_of_gr":True,
      "data_public_via_ilrs":True,
    }
  },
  "ilrs_2026": {
    "facts":{
      "predicted_lageos_mas_per_year":30.650,
      "predicted_lares2_mas_per_year":30.678,
      "reported_uncertainty_fraction":2e-3,
    }
  }
}


def main():
    n=SOURCES["nature_2026"]["facts"]
    i=SOURCES["ilrs_2026"]["facts"]
    architecture_overdetermined=(
      n["uses_lares2_and_lageos"] and
      n["uses_grace_gravity_models"] and
      n["combined_nodal_residuals"] and
      n["data_public_via_ilrs"]
    )
    independent_background_constraint=n["uses_grace_gravity_models"]
    multi_satellite_target=n["uses_lares2_and_lageos"]
    orientation_sensitive_target=True  # frame-dragging nodal precession changes sign with orbit orientation relative to spin
    precision_good=n["relative_uncertainty"] <= 0.0021
    agrees_with_gr=n["reported_stringent_confirmation_of_gr"]
    new_loop_residual_detected=False if agrees_with_gr else None

    status=(
      "REAL_SATELLITE_CONTROL_PASS_NO_NEW_RESIDUAL"
      if architecture_overdetermined and independent_background_constraint and multi_satellite_target and orientation_sensitive_target and precision_good and agrees_with_gr
      else "REAL_SATELLITE_GATE_INCONCLUSIVE"
    )

    result={
      "schema":"ckk.external.satellite-loop-evidence.v1",
      "status":status,
      "sources":SOURCES,
      "tests":{
        "background_field_independently_constrained":independent_background_constraint,
        "multiple_satellites":multi_satellite_target,
        "global_orientation_sensitive_observable":orientation_sensitive_target,
        "overdetermined_architecture":architecture_overdetermined,
        "published_precision_le_0p21pct":precision_good,
        "published_result_agrees_with_GR":agrees_with_gr,
        "new_unexplained_global_residual_detected":new_loop_residual_detected,
      },
      "predicted_frame_dragging_mas_per_year":{
        "LAGEOS":i["predicted_lageos_mas_per_year"],
        "LARES2":i["predicted_lares2_mas_per_year"],
      },
      "interpretation":"This real satellite experiment has the overdetermined structure we wanted: independent gravity-field information plus two satellite orbital observables and an orientation-sensitive global term. The published 2026 result agrees with GR at about 2e-3 relative uncertainty, so it validates the measurement architecture but does not reveal a new leftover term.",
      "claim_boundary":"This script does not re-fit ILRS normal points or GEODYN residuals. It gates published evidence only. A true discovery test requires downloading raw/normal-point data, freezing nuisance models, fitting on one subset/channel, and testing held-out satellites/arcs for a common residual with predeclared scaling and sign."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if status.startswith("REAL_SATELLITE_CONTROL_PASS") else 1)

if __name__=="__main__": main()
