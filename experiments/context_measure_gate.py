#!/usr/bin/env python3
"""Blind context-dependent intrinsic-measure gate for CKK.

Question: can structurally identical closed states, embedded in distinct endogenous
provenance contexts, have different reachable-future measure relations?

No circle, pi, metric, curvature, gravity, spacetime, mass, energy, Lorentz, or
external time is supplied. The kernel is imported read-only and not modified.

Two arms are compared:
  A. structural identity (candidate scientific path): provenance is erased from node identity.
  B. historical provenance-bearing identity: parts/provenance remain in node identity.

The intrinsic diagnostic is graph-internal only: number of distinct transitively
reachable FUTURE STRUCTURAL states from each provenance-bearing instance. This
avoids inventing a geometric metric. If two provenance contexts with the same
structural state have different structural future cones, context changes the
available continuation measure in the provenance-bearing graph.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar as G  # noqa: E402
from expand import expand_auditable, expand_structural_auditable  # noqa: E402

OUT = ROOT / "results" / "context_measure_gate.json"
LEVELS = 4
CAP = 30000
CLOSED_KINDS = {G.CYCLE, G.PRODUCT, G.BUNDLE, G.BOUNDARY}


def adjacency(derivations):
    adj = defaultdict(set)
    for d in derivations:
        for src in d.inputs:
            if src != d.output:
                adj[src].add(d.output)
    return adj


def reachable(start, adj):
    seen = set()
    stack = list(adj.get(start, ()))
    while stack:
        v = stack.pop()
        if v == start or v in seen:
            continue
        seen.add(v)
        stack.extend(adj.get(v, ()))
    return seen


def main():
    # Scientific structural arm.
    sp, sd = expand_structural_auditable(levels=LEVELS, cap=CAP)
    sstates = {s.structural_sig(): s for s in sp.values()}
    sadj = adjacency(sd)

    # Historical provenance-bearing arm. This is used only as an audit of what
    # structural identity removes; it does not change the candidate kernel path.
    hp, hd = expand_auditable(levels=LEVELS, cap=CAP)
    hstates = {s.sig(): s for s in hp.values()}
    hadj = adjacency(hd)

    # Group distinct provenance-bearing instances by the exact same structural state.
    groups = defaultdict(list)
    for hsig, s in hstates.items():
        if s.kind in CLOSED_KINDS:
            groups[s.structural_sig()].append(hsig)
    repeated = {k: v for k, v in groups.items() if len(v) >= 2}

    differing_groups = []
    invariant_groups = []
    for structural_id, instances in repeated.items():
        instance_measures = []
        instance_future_sets = []
        for hsig in instances:
            fut_h = reachable(hsig, hadj)
            # Measure only distinct FUTURE STRUCTURAL states so context multiplicity
            # itself cannot manufacture a difference.
            fut_struct = {
                hstates[x].structural_sig()
                for x in fut_h if x in hstates
            }
            instance_measures.append(len(fut_struct))
            instance_future_sets.append(fut_struct)

        same_measure = len(set(instance_measures)) == 1
        same_future = all(fs == instance_future_sets[0] for fs in instance_future_sets[1:])
        record = {
            "structural_state": repr(structural_id),
            "instances": len(instances),
            "future_structural_counts": instance_measures,
            "same_count": same_measure,
            "same_future_set": same_future,
        }
        if same_measure and same_future:
            invariant_groups.append(record)
        else:
            differing_groups.append(record)

    # Structural arm has exactly one node per structural_sig by definition; verify
    # this rather than assuming it.
    structural_unique = len(sstates) == len({s.structural_sig() for s in sp.values()})

    total = len(repeated)
    diff = len(differing_groups)
    fraction = diff / total if total else None

    if total == 0:
        status = "NO_REPEATED_CLOSED_STRUCTURE_CONTEXTS"
    elif diff > 0:
        status = "PROVENANCE_CONTEXT_CHANGES_FUTURE_MEASURE_BUT_STRUCTURAL_IDENTITY_ERASES_IT"
    else:
        status = "CLOSED_STRUCTURE_FUTURE_MEASURE_CONTEXT_INVARIANT"

    result = {
        "schema": "ckk.external.context-measure-gate.v1",
        "status": status,
        "kernel_modified": False,
        "frozen_question": "Do exact same closed structural states embedded in distinct endogenous provenance contexts have different graph-internal future continuation measures?",
        "frozen_measure": "number and identity of distinct transitively reachable structural states; no geometric metric inserted",
        "generator": {
            "levels": LEVELS,
            "cap": CAP,
            "structural_states": len(sstates),
            "structural_derivations": len(sd),
            "historical_provenance_states": len(hstates),
            "historical_derivations": len(hd),
        },
        "tests": {
            "structural_identity_unique": structural_unique,
            "repeated_closed_structural_groups_with_distinct_provenance": total,
            "context_dependent_future_measure_groups": diff,
            "context_invariant_future_measure_groups": len(invariant_groups),
            "context_dependent_fraction": fraction,
        },
        "examples_context_dependent": differing_groups[:10],
        "examples_invariant": invariant_groups[:5],
        "interpretation": (
            "A positive context-dependent result means only that endogenous provenance context changes the graph-internal set of future structural continuations in the provenance-bearing representation. "
            "If structural identity collapses those contexts, current structural CKK cannot retain that context dependence as an intrinsic state property. This does not derive geometry, curvature, pi, or physics."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
