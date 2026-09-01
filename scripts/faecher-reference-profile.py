#!/usr/bin/env python3
"""Profile the unchanged, provenance-bearing FAECHER level expander.

This deliberately mirrors ``expand._expand_core``.  It is measurement code,
not the scalable implementation: the same full ``Struct.sig()`` values, full
ordered Cartesian products, operator order, level snapshots, and duplicate
derivation events are retained.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import resource
import sys
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar  # noqa: E402
from expand import Derivation  # noqa: E402


def rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def deep_size(root: object) -> int:
    """Exact reachable Python heap size under ``sys.getsizeof`` semantics."""
    seen: set[int] = set()

    def visit(value: object) -> int:
        identity = id(value)
        if identity in seen:
            return 0
        seen.add(identity)
        total = sys.getsizeof(value)
        if isinstance(value, dict):
            total += sum(visit(k) + visit(v) for k, v in value.items())
        elif isinstance(value, (tuple, list, set, frozenset)):
            total += sum(visit(item) for item in value)
        elif hasattr(value, "__dict__"):
            total += visit(vars(value))
        return total

    return visit(root)


def profile(levels: int) -> dict:
    tracemalloc.start(25)
    started = time.perf_counter()
    sig_seconds = 0.0
    dispatch_seconds = 0.0
    membership_seconds = 0.0

    def signature(state):
        nonlocal sig_seconds
        tick = time.perf_counter()
        result = state.sig()
        sig_seconds += time.perf_counter() - tick
        return result

    pool = {signature(seed): seed for seed in grammar.SEEDS}
    derivations: list[Derivation] = []
    level_rows = []
    operator_totals: dict[str, Counter] = {
        op.__name__: Counter() for op in grammar.UNARY + grammar.BINARY
    }

    for level in range(1, levels + 1):
        items = list(pool.values())
        new = {}
        level_ops = {name: Counter() for name in operator_totals}
        duplicate_states = 0
        successful_results = 0

        def offer(op, inputs, output) -> None:
            nonlocal duplicate_states, membership_seconds, successful_results
            if output is None:
                return
            successful_results += 1
            for table in (operator_totals[op.__name__], level_ops[op.__name__]):
                table["successful"] += 1
            input_ids = tuple(signature(state) for state in inputs)
            target_id = signature(output)
            if target_id in input_ids:
                for table in (operator_totals[op.__name__], level_ops[op.__name__]):
                    table["idempotent_rejected"] += 1
                return
            derivations.append(Derivation(op.__name__, input_ids, target_id, level))
            tick = time.perf_counter()
            exists = target_id in pool or target_id in new
            membership_seconds += time.perf_counter() - tick
            if exists:
                duplicate_states += 1
                for table in (operator_totals[op.__name__], level_ops[op.__name__]):
                    table["duplicate_children"] += 1
            else:
                new[target_id] = output
                for table in (operator_totals[op.__name__], level_ops[op.__name__]):
                    table["unique_children"] += 1

        for state in items:
            for operator in grammar.UNARY:
                operator_totals[operator.__name__]["attempted"] += 1
                level_ops[operator.__name__]["attempted"] += 1
                tick = time.perf_counter()
                result = operator(state)
                dispatch_seconds += time.perf_counter() - tick
                offer(operator, (state,), result)

        for left in items:
            for right in items:
                for operator in grammar.BINARY:
                    operator_totals[operator.__name__]["attempted"] += 1
                    level_ops[operator.__name__]["attempted"] += 1
                    tick = time.perf_counter()
                    result = operator(left, right)
                    dispatch_seconds += time.perf_counter() - tick
                    offer(operator, (left, right), result)

        pool.update(new)
        level_rows.append(
            {
                "level": level,
                "pool_before": len(items),
                "candidate_binary_pairs": len(items) ** 2,
                "binary_operator_dispatches": len(items) ** 2 * len(grammar.BINARY),
                "new_states": len(new),
                "total_states": len(pool),
                "max_dim": max(state.dim for state in pool.values()),
                "successful_operator_results": successful_results,
                "duplicates_rejected": duplicate_states,
                "derivation_events_total": len(derivations),
                "peak_rss_bytes": rss_bytes(),
                "operator_counts": {
                    name: dict(counts) for name, counts in level_ops.items()
                },
            }
        )

    current, traced_peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    top = []
    for stat in snapshot.statistics("lineno")[:15]:
        frame = stat.traceback[0]
        top.append(
            {
                "file": str(Path(frame.filename).resolve().relative_to(ROOT))
                if str(Path(frame.filename).resolve()).startswith(str(ROOT))
                else frame.filename,
                "line": frame.lineno,
                "bytes": stat.size,
                "allocations": stat.count,
            }
        )

    timings = {
        "wall_seconds": time.perf_counter() - started,
        "struct_sig_seconds": sig_seconds,
        "structural_sig_seconds": 0.0,
        "operator_dispatch_seconds": dispatch_seconds,
        "dict_equality_membership_seconds": membership_seconds,
    }
    return {
        "schema": "ckk.faecher-reference-profile.v1",
        "mode": "UNCHANGED_HISTORICAL_STRUCT_SIG",
        "levels": level_rows,
        "final": {
            "states": len(pool),
            "derivation_events": len(derivations),
            "max_dim": max(state.dim for state in pool.values()),
            "peak_rss_bytes": rss_bytes(),
            "tracemalloc_current_bytes": current,
            "tracemalloc_peak_bytes": traced_peak,
            "pool_deep_bytes": deep_size(pool),
            "provenance_deep_bytes": deep_size(derivations),
        },
        "timings": timings,
        "operator_totals": {
            name: dict(counts) for name, counts in operator_totals.items()
        },
        "dominant_allocations": top,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = profile(args.levels)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
