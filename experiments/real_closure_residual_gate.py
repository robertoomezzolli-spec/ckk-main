#!/usr/bin/env python3
"""Literature-grounded real-world residual gate.

CKK kernel is read-only. This is not a physics engine; it evaluates whether
published precision closed-loop / geodetic experiments currently establish a
persistent unexplained residual after known geometry/systematics are modeled.

Frozen gate: PASS_NEW_STATE only if independent sources report a reproducible,
nonzero, model-corrected residual that survives known systematic corrections
and is not attributed to measurement/model error. Otherwise NO_EVIDENCE.
"""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"results"/"real_closure_residual_gate.json"

sources=[
 {"id":"WETTZELL_G_RING_2022","kind":"closed optical ring","reported":"After laser-systematic extraction, residuals are mostly white-noise; Allan deviation falls below 1e-9 of Earth rotation after ~1e4 s.","persistent_unexplained_residual":False,"url":"https://link.springer.com/article/10.1140/epjc/s10052-022-10798-9"},
 {"id":"GINGERINO_2020","kind":"closed optical ring","reported":"Geodetic signals are recovered; sensitivity approaches the regime required for terrestrial GR tests, but no new persistent residual is reported.","persistent_unexplained_residual":False,"url":"https://journals.aps.org/prresearch/abstract/10.1103/PhysRevResearch.2.032069"},
 {"id":"APOLLO_LLR_2023","kind":"laser-ranging orbital geometry","reported":"Sub-mm measurement uncertainty is achieved, but ephemeris/model inaccuracies still contribute to residuals; no mm-accurate ephemeris model exists.","persistent_unexplained_residual":False,"url":"https://doi.org/10.1088/1538-3873/ACEB2F"},
 {"id":"SLR_GNSS_2015","kind":"satellite laser ranging","reported":"Mean residuals at ~-13 mm are discussed with named atmospheric, reflector, radiation-pressure, ionosphere and antenna-offset systematics that can reduce them.","persistent_unexplained_residual":False,"url":"https://link.springer.com/article/10.1007/s00190-015-0810-8"}
]

independent=len(sources)>=2
unexplained=[s for s in sources if s["persistent_unexplained_residual"]]
status="PASS_NEW_STATE" if independent and len(unexplained)>=2 else "NO_EVIDENCE_FOR_NEW_STATE"
result={"schema":"ckk.external.real-closure-residual-gate.v1","status":status,"sources":sources,"tests":{"independent_sources":independent,"at_least_two_persistent_unexplained_residuals":len(unexplained)>=2},"interpretation":"Published precision closed-loop/geodetic results checked here do not establish a universal residual that survives known geometry and systematic corrections. Existing residuals are either whitened by correction or explicitly model/systematic limited.","claim_boundary":"This does not prove that no missing state exists. It says the current selected real-world evidence does not justify one. A positive claim requires raw/independent data with a reproducible post-correction residual and a predeclared scale/signature."}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2)); raise SystemExit(0)
