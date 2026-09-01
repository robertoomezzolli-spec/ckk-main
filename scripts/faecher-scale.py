#!/usr/bin/env python3
"""Run or inspect the exact disk-backed FAECHER level expansion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

from stream_expand import ComputeLimits, open_engine  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--target-level", type=int, required=True)
    parser.add_argument("--wall-seconds", type=float, default=600)
    parser.add_argument("--ram-mb", type=float, default=1_024)
    parser.add_argument("--minimum-free-disk-mb", type=float, default=2_048)
    parser.add_argument("--node-cap", type=int)
    parser.add_argument("--derivation-cap", type=int)
    parser.add_argument("--batch-size", type=int, default=2_000)
    parser.add_argument("--symbolic-product-threshold", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    limits = ComputeLimits(
        wall_seconds=args.wall_seconds,
        ram_mb=args.ram_mb,
        minimum_free_disk_mb=args.minimum_free_disk_mb,
        node_cap=args.node_cap,
        derivation_cap=args.derivation_cap,
    )
    engine = open_engine(
        args.database,
        limits,
        batch_size=args.batch_size,
        symbolic_product_threshold=args.symbolic_product_threshold,
    )
    try:
        run = engine.run_to_level(args.target_level)
        result = {
            "schema": "ckk.faecher-scale.v1",
            "compute_limits": {
                "wall_seconds": args.wall_seconds,
                "ram_mb": args.ram_mb,
                "minimum_free_disk_mb": args.minimum_free_disk_mb,
                "node_cap": args.node_cap,
                "derivation_cap": args.derivation_cap,
            },
            "run": run,
            "analysis": engine.analysis(),
        }
    finally:
        engine.close()
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
