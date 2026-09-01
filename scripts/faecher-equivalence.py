#!/usr/bin/env python3
"""Create exact-content fingerprints for reference or SQLite FAECHER runs.

Every historical recursive tuple is reconstructed.  The manifest compares the
sorted list of SHA-256 content digests plus cardinality; it never compares
snapshot-derived cosmetic fields or database-local IDs.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

from expand import expand_auditable  # noqa: E402
from stream_expand import ComputeLimits, open_engine  # noqa: E402


def digest(value: object) -> bytes:
    return hashlib.sha256(repr(value).encode("utf-8")).digest()


def manifest(values) -> dict:
    items = sorted({digest(value) for value in values})
    return {
        "count": len(items),
        "sha256": hashlib.sha256(b"".join(items)).hexdigest(),
    }


def reference(levels: int) -> dict:
    rows = []
    for level in range(1, levels + 1):
        pool, derivations = expand_auditable(levels=level, cap=10**9)
        events = defaultdict(set)
        for event in derivations:
            events[event.operator].add(digest(event.event_key()))
        all_events = set().union(*events.values()) if events else set()
        rows.append(
            {
                "level": level,
                "states": manifest(pool),
                "derivations": {
                    "count": len(all_events),
                    "sha256": hashlib.sha256(b"".join(sorted(all_events))).hexdigest(),
                },
                "operators": {
                    name: {
                        "count": len(items),
                        "sha256": hashlib.sha256(b"".join(sorted(items))).hexdigest(),
                    }
                    for name, items in sorted(events.items())
                },
                "max_dim": max(state.dim for state in pool.values()),
            }
        )
    return {"mode": "REFERENCE", "levels": rows}


def database(path: Path, levels: int) -> dict:
    limits = ComputeLimits(3600, 100_000, 1)
    engine = open_engine(path, limits)
    try:
        signature_cache: dict[int, tuple] = {}
        rows = []
        for level in range(1, levels + 1):
            state_ids = [
                row[0]
                for row in engine.connection.execute(
                    "SELECT id FROM states WHERE born_level<=? ORDER BY id", (level,)
                )
            ]
            signatures = {
                state_id: engine.reconstruct_signature(state_id, signature_cache)
                for state_id in state_ids
            }
            events = defaultdict(set)
            for operator, input_a, input_b, output in engine.connection.execute(
                "SELECT operator,input_a,input_b,output FROM derivations "
                "WHERE first_level<=? ORDER BY id",
                (level,),
            ):
                inputs = (signatures[input_a],)
                if input_b:
                    inputs += (signatures[input_b],)
                if operator == "op_product":
                    inputs = tuple(sorted(inputs))
                events[operator].add(digest((operator, inputs, signatures[output])))
            all_events = set().union(*events.values()) if events else set()
            rows.append(
                {
                    "level": level,
                    "states": manifest(signatures.values()),
                    "derivations": {
                        "count": len(all_events),
                        "sha256": hashlib.sha256(b"".join(sorted(all_events))).hexdigest(),
                    },
                    "operators": {
                        name: {
                            "count": len(items),
                            "sha256": hashlib.sha256(b"".join(sorted(items))).hexdigest(),
                        }
                        for name, items in sorted(events.items())
                    },
                    "max_dim": max(signature[1] for signature in signatures.values()),
                }
            )
        return {"mode": "DATABASE", "levels": rows}
    finally:
        engine.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("reference", "database"), required=True)
    parser.add_argument("--levels", type=int, default=5)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "reference":
        result = reference(args.levels)
    else:
        if args.database is None:
            parser.error("--database is required in database mode")
        result = database(args.database, args.levels)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
