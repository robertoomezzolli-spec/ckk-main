#!/usr/bin/env python3
"""Emit one provenance-complete Scientific generation without database writes."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

from expand import expand_structural_auditable  # noqa: E402
from grammar import MAXDIM, SEEDS  # noqa: E402


def stable_json(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def digest(value):
    payload = value if isinstance(value, str) else stable_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_id(prefix, value):
    return f"{prefix}_{digest(value)[:24]}"


def signature(struct):
    return {
        "kind": struct.kind,
        "dim": struct.dim,
        "order": struct.order,
        "sym": struct.sym,
        "sq": struct.sq,
        "anti": struct.anti,
        "mult": struct.mult,
        "bc": struct.bc,
        "dual": struct.dual,
        "occ": struct.occ,
    }


def signature_from_tuple(value):
    kind, dim, order, sym, sq, anti, mult, bc, dual, occ = value

    def decode(item):
        if item == "None":
            return None
        if item == "True":
            return True
        if item == "False":
            return False
        return item

    return {
        "kind": kind,
        "dim": dim,
        "order": order,
        "sym": decode(sym),
        "sq": None if sq == "None" else int(sq),
        "anti": decode(anti),
        "mult": mult,
        "bc": decode(bc),
        "dual": dual,
        "occ": None if occ == "None" else int(occ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", type=int, default=1)
    parser.add_argument("--cap", type=int, default=1200)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--operator-version", default="ckk-grammar-v1")
    args = parser.parse_args()
    if args.levels < 0 or args.cap < 1:
        raise SystemExit("levels and cap must be non-negative")

    pool, raw_events = expand_structural_auditable(levels=args.levels, cap=args.cap)
    seed_signatures = {seed.structural_sig() for seed in SEEDS}
    by_tuple = {}
    structures = []
    for key, struct in sorted(pool.items(), key=lambda item: stable_json(signature(item[1]))):
        sig = signature(struct)
        structural_hash = digest(sig)
        structure_id = make_id("str", structural_hash)
        by_tuple[key] = {"id": structure_id, "hash": structural_hash}
        structures.append({
            "generation_id": args.generation_id,
            "id": structure_id,
            "kind": struct.kind,
            "dim": struct.dim,
            "recurrence_order": struct.order,
            "sym": struct.sym,
            "sq": struct.sq,
            "anti": struct.anti,
            "mult": struct.mult,
            "bc": struct.bc,
            "dual": struct.dual,
            "occ": struct.occ,
            "lifecycle": "ADMITTED" if key in seed_signatures else "GENERABLE",
            "structural_sig": sig,
            "structural_hash": structural_hash,
        })

    unique_events = {}
    for raw in raw_events:
        identity = raw.event_key()
        input_keys = list(identity[1])
        output_key = identity[2]
        if any(key not in by_tuple for key in input_keys) or output_key not in by_tuple:
            continue
        inputs = [by_tuple[key]["id"] for key in input_keys]
        input_hashes = [by_tuple[key]["hash"] for key in input_keys]
        if raw.operator == "op_product":
            paired = sorted(zip(inputs, input_hashes))
            inputs = [item[0] for item in paired]
            input_hashes = [item[1] for item in paired]
        event = {
            "generation_id": args.generation_id,
            "operator": raw.operator,
            "operator_version": args.operator_version,
            "inputs": inputs,
            "output": by_tuple[output_key]["id"],
            "parameters": {"arity": len(inputs)},
            "level": raw.level,
            "input_structural_hashes": input_hashes,
            "output_structural_hash": by_tuple[output_key]["hash"],
        }
        event_identity = {key: value for key, value in event.items() if key != "generation_id"}
        event_hash = digest(event_identity)
        event["event_hash"] = event_hash
        event["id"] = make_id("dev", event_hash)
        unique_events[event_hash] = event

    events = sorted(unique_events.values(), key=lambda item: (item["level"], item["operator"], item["id"]))
    output = {
        "generation_id": args.generation_id,
        "experiment": {"maxdim": MAXDIM, "levels": args.levels, "cap": args.cap},
        "self_duality": {"assessment": "NOT_EVALUATED", "equivalence_relation": None},
        "structures": structures,
        "derivation_events": events,
    }
    print(json.dumps(output, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()

