#!/usr/bin/env python3
from __future__ import annotations
import itertools, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "experiments" / "cycle_2pi_heldout_targets.json"
OUT = ROOT / "results" / "cycle_2pi_blind" / "heldout_external.json"


def score(features, motif):
    return sum(int(features[k] == motif[k]) for k in motif)


def exact_permutation_p(pos_scores, neg_scores):
    vals = pos_scores + neg_scores
    npos = len(pos_scores)
    observed = sum(pos_scores)/len(pos_scores) - sum(neg_scores)/len(neg_scores)
    ge = 0; total = 0
    for comb in itertools.combinations(range(len(vals)), npos):
        s = set(comb)
        a = [vals[i] for i in range(len(vals)) if i in s]
        b = [vals[i] for i in range(len(vals)) if i not in s]
        diff = sum(a)/len(a) - sum(b)/len(b)
        total += 1
        if diff >= observed - 1e-12:
            ge += 1
    return observed, ge/total, total


def main():
    m = json.loads(TARGETS.read_text())
    motif = m["sealed_motif"]
    pos = [{**x, "score": score(x["features"], motif)} for x in m["positive_targets"]]
    neg = [{**x, "score": score(x["features"], motif)} for x in m["negative_controls"]]
    transfer = [{**x, "score": score(x["features"], motif)} for x in m["transfer_targets"]]
    obs, p, nperm = exact_permutation_p([x["score"] for x in pos],[x["score"] for x in neg])
    full_match_controls = [x["id"] for x in neg if x["score"] == len(motif)]
    gate = m["primary_gate"]
    enrichment_pass = obs > 0 and p <= gate["permutation_p_max"]
    specificity_pass = len(full_match_controls) <= gate["max_full_match_controls"]
    status = "HELDOUT_PASS" if enrichment_pass and specificity_pass else "HELDOUT_FAIL"
    result = {
      "schema":"ckk.cycle-2pi-blind.heldout.v1",
      "status":status,
      "sealed_motif":motif,
      "positive":pos,
      "negative":neg,
      "transfer":transfer,
      "primary":{
        "mean_score_positive":sum(x["score"] for x in pos)/len(pos),
        "mean_score_negative":sum(x["score"] for x in neg)/len(neg),
        "difference":obs,
        "exact_one_sided_permutation_p":p,
        "permutations":nperm,
        "enrichment_pass":enrichment_pass,
        "full_match_controls":full_match_controls,
        "full_match_control_count":len(full_match_controls),
        "specificity_pass":specificity_pass
      },
      "claim_boundary":"Held-out test attacks specificity of sealed CYCLE->WINDING. A statistical enrichment can coexist with failure of specificity. Any full-match classical control shows the motif is not by itself a unique signature of 2pi phase/topological quantization."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
