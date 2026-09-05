#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "experiments" / "cycle_2pi_stage_b_targets.json"
OUT = ROOT / "results" / "cycle_2pi_blind" / "stage_b_external.json"

SEALED_MOTIF = {"cycle": 1, "integer_winding": 1}


def score(features):
    # exact two-feature structural match; no fitted weights.
    return sum(int(features[k] == SEALED_MOTIF[k]) for k in SEALED_MOTIF)


def exact_permutation_p(pos_scores, neg_scores):
    vals = pos_scores + neg_scores
    npos = len(pos_scores)
    observed = sum(pos_scores)/npos - sum(neg_scores)/len(neg_scores)
    ge = 0; total = 0
    idx = range(len(vals))
    for comb in itertools.combinations(idx, npos):
        s = set(comb)
        a = [vals[i] for i in idx if i in s]
        b = [vals[i] for i in idx if i not in s]
        diff = sum(a)/len(a) - sum(b)/len(b)
        total += 1
        if diff >= observed - 1e-12:
            ge += 1
    return observed, ge/total, total


def main():
    m = json.loads(TARGETS.read_text())
    pos = [{**x, "score": score(x["features"])} for x in m["positive_targets"]]
    neg = [{**x, "score": score(x["features"])} for x in m["negative_controls"]]
    transfer = [{**x, "score": score(x["features"])} for x in m["transfer_targets"]]
    obs, p, nperm = exact_permutation_p([x["score"] for x in pos],[x["score"] for x in neg])
    result = {
      "schema":"ckk.cycle-2pi-blind.stage-b.v1",
      "status":"STAGE_B_PASS" if obs > 0 and p <= 0.05 else "STAGE_B_FAIL",
      "sealed_motif":SEALED_MOTIF,
      "positive":pos,
      "negative":neg,
      "transfer":transfer,
      "primary":{"mean_score_positive":sum(x["score"] for x in pos)/len(pos),
                 "mean_score_negative":sum(x["score"] for x in neg)/len(neg),
                 "difference":obs,"exact_one_sided_permutation_p":p,"permutations":nperm},
      "claim_boundary":"Stage B tests enrichment of the already-sealed abstract CYCLE->WINDING motif against an external, frozen physical benchmark set. It does not show that CKK derives pi, 2*pi, constants, or any physical law. The target abstraction itself is human-specified and therefore this is a structural correspondence test, not a discovery claim."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"]=="STAGE_B_PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
