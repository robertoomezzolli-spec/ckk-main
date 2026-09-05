#!/usr/bin/env python3
"""Primitive-identification vs limit experiment.

KERNEL POLICY: CKK kernel is read-only. This is an external harness.

Question frozen before run:
Can exact closure be represented by primitive endpoint identification without
LIMIT, DISTANCE, polygons, pi, or approximation, while any finite linear
reconstruction of that same closed object retains nonzero closure error?

This is an architecture test, not a claim that standard analysis is incomplete.
"""
from __future__ import annotations
import json, math
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]/"results"/"primitive_identification_vs_limit.json"
NS=[3,4,6,8,16,32,64,128,256,1024,4096,16384]

# Abstract quotient: labels differing by integer multiples of T are identical.
# T deliberately = 1: no pi/circle semantics.
T=1.0

def same_class(x,y):
    d=(x-y)/T
    return abs(d-round(d)) < 1e-14


def finite_linear_reconstruction_error(n):
    # Reconstruct a smooth closed unit-period embedding from n straight chords.
    # pi occurs only inside this external observation model; the primitive
    # quotient above knows nothing about it. Relative perimeter deficit > 0
    # for every finite n and tends to 0.
    exact=2*math.pi
    approx=2*n*math.sin(math.pi/n)
    return (exact-approx)/exact


def main():
    primitive_tests=[]
    for k in [-7,-2,-1,0,1,2,11]:
        primitive_tests.append({"k":k,"identified":same_class(0.0,k*T)})
    primitive_exact=all(x["identified"] for x in primitive_tests)

    rows=[{"N":n,"relative_deficit":finite_linear_reconstruction_error(n)} for n in NS]
    finite_never_exact=all(r["relative_deficit"]>0 for r in rows)
    converges=all(rows[i+1]["relative_deficit"]<rows[i]["relative_deficit"] for i in range(len(rows)-1))
    final_smaller=rows[-1]["relative_deficit"] < rows[0]["relative_deficit"]

    # Representation invariance: rescaling the coordinate must preserve the
    # integer class label; closure is relation, not a privileged period value.
    scales=[0.125,0.5,1.0,3.0,17.0]
    scale_checks=[]
    for a in scales:
        ok=True
        for k in range(-8,9):
            ratio=(a*k*T)/(a*T)
            ok &= abs(ratio-round(ratio))<1e-14
        scale_checks.append({"scale":a,"integer_class_preserved":ok})
    coordinate_invariant=all(x["integer_class_preserved"] for x in scale_checks)

    passed=primitive_exact and finite_never_exact and converges and final_smaller and coordinate_invariant
    result={
      "schema":"ckk.external.primitive-identification-vs-limit.v1",
      "status":"PRIMITIVE_IDENTIFICATION_PASS" if passed else "PRIMITIVE_IDENTIFICATION_FAIL",
      "primitive_space":"R / T Z with T=1",
      "primitive_uses_pi":False,
      "primitive_uses_limit":False,
      "primitive_uses_distance":False,
      "primitive_tests":primitive_tests,
      "finite_reconstruction":rows,
      "scale_checks":scale_checks,
      "tests":{
        "primitive_endpoint_identification_exact":primitive_exact,
        "finite_linear_reconstruction_never_exact":finite_never_exact,
        "finite_error_monotonically_converges":converges,
        "closure_class_coordinate_invariant":coordinate_invariant
      },
      "interpretation":"Exact closure can be encoded as an equivalence/identification relation, whereas this finite linear reconstruction approaches the same closed embedding only asymptotically.",
      "claim_boundary":"This distinguishes two representations of closure. It does NOT prove that pi is wrong, that limits are defective, that brains/computers cannot represent circles, or that mathematics lacks a known relation. A stronger novelty claim would require showing that CKK independently generates the identification architecture and that it predicts something standard quotient/topological descriptions do not."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if passed else 1)

if __name__=="__main__": main()
