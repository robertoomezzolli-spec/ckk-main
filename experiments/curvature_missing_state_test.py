#!/usr/bin/env python3
"""External curvature/missing-state test.

CKK KERNEL IS READ-ONLY.

Frozen question:
Can an exactly closed geodesic circle look like an "imperfect Euclidean circle"
if a state variable (curvature) is omitted, and does restoring that variable
remove the residual?

Arms:
- FLAT: K=0, Euclidean evaluation must return pi exactly (within fp tolerance).
- POSITIVE_CURVATURE: sphere-like constant K>0. Euclidean estimator C/(2r)
  must deviate below pi for finite r.
- NEGATIVE_CURVATURE: hyperbolic-like constant K<0. Euclidean estimator must
  deviate above pi for finite r.
- CORRECTED: use the correct constant-curvature geodesic circumference law;
  recovered invariant must return pi in every arm.

This is not evidence that physical pi is wrong. It tests whether an omitted
geometric state can create a systematic "circle residual" that vanishes when
the missing state is restored.
"""
from __future__ import annotations
import json, math
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"results"/"curvature_missing_state.json"
TOL=1e-12
RADII=[0.02,0.05,0.1,0.2,0.35,0.5]


def S_K(r,K):
    if abs(K)<1e-15:
        return r
    if K>0:
        q=math.sqrt(K)
        return math.sin(q*r)/q
    q=math.sqrt(-K)
    return math.sinh(q*r)/q


def circumference(r,K):
    return 2*math.pi*S_K(r,K)


def arm(name,K):
    rows=[]
    for r in RADII:
        C=circumference(r,K)
        naive=C/(2*r)
        corrected=C/(2*S_K(r,K))
        rows.append({
            "r":r,
            "C":C,
            "naive_pi_estimate":naive,
            "naive_residual":naive-math.pi,
            "corrected_pi_estimate":corrected,
            "corrected_residual":corrected-math.pi,
        })
    return {"name":name,"K":K,"rows":rows}


def main():
    flat=arm("flat",0.0)
    pos=arm("positive_curvature",1.0)
    neg=arm("negative_curvature",-1.0)

    flat_exact=all(abs(x["naive_residual"])<TOL for x in flat["rows"])
    pos_sign=all(x["naive_residual"]<0 for x in pos["rows"])
    neg_sign=all(x["naive_residual"]>0 for x in neg["rows"])
    corrected_all=all(abs(x["corrected_residual"])<TOL for a in [flat,pos,neg] for x in a["rows"])
    pos_magnitude_grows=all(abs(pos["rows"][i+1]["naive_residual"])>abs(pos["rows"][i]["naive_residual"]) for i in range(len(RADII)-1))
    neg_magnitude_grows=all(abs(neg["rows"][i+1]["naive_residual"])>abs(neg["rows"][i]["naive_residual"]) for i in range(len(RADII)-1))

    passed=flat_exact and pos_sign and neg_sign and corrected_all and pos_magnitude_grows and neg_magnitude_grows
    result={
      "schema":"ckk.external.curvature-missing-state.v1",
      "status":"MISSING_CURVATURE_STATE_PASS" if passed else "MISSING_CURVATURE_STATE_FAIL",
      "tests":{
        "flat_euclidean_exact":flat_exact,
        "positive_curvature_residual_negative":pos_sign,
        "negative_curvature_residual_positive":neg_sign,
        "residual_magnitude_grows_with_scale_positive_K":pos_magnitude_grows,
        "residual_magnitude_grows_with_scale_negative_K":neg_magnitude_grows,
        "restoring_curvature_removes_residual":corrected_all,
      },
      "arms":{"flat":flat,"positive":pos,"negative":neg},
      "interpretation":"An exactly closed geodesic circle can yield a systematic non-pi value under a Euclidean circumference/radius estimator when curvature is omitted. Including the curvature-dependent radial map restores pi exactly in this constant-curvature model.",
      "claim_boundary":"This demonstrates a missing-state mechanism using standard non-Euclidean geometry. It does not show that pi is physically wrong, that real circles possess an unknown extra variable beyond known spacetime geometry, or that gravity is hidden inside pi. A physical claim would require independent real-world residual data unexplained by the accepted metric/curvature model."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if passed else 1)

if __name__=="__main__": main()
