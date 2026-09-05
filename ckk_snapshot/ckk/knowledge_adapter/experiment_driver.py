"""Fixed operational entrypoints used by the networkless experiment worker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


def equivalence(source: Path, output: Path) -> None:
    sys.path.insert(0, str(source / "experiments"))
    import fresh_seed_closure_plateau_gate_v2_fast as fast  # type: ignore

    reports = fast.prove_equivalence()
    required = (
        "state_set_equal",
        "first_seen_equal",
        "edge_set_equal",
        "fiber_pair_set_equal",
        "unique_event_count_equal",
        "cap_status_equal",
    )
    passed = bool(reports) and all(
        report.get("pass") is True and all(report.get(field) is True for field in required)
        for report in reports.values()
    )
    payload = {
        "schema_version": 1,
        "status": "PASSED" if passed else "FAILED",
        "equivalence_passed": passed,
        "required_equalities": list(required),
        "contexts": reports,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit(2)


def smoke(output: Path) -> None:
    started = time.time()
    while time.time() - started < 45:
        output.write_text(
            json.dumps({"status": "RUNNING", "started_at": started, "heartbeat_at": time.time()}, sort_keys=True),
            encoding="utf-8",
        )
        time.sleep(0.25)
    output.write_text(
        json.dumps({"status": "COMPLETED", "started_at": started, "finished_at": time.time()}, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("equivalence")
    check.add_argument("--source", required=True)
    check.add_argument("--output", required=True)
    test = subparsers.add_parser("smoke")
    test.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "equivalence":
        equivalence(Path(args.source), Path(args.output))
    else:
        smoke(Path(args.output))


if __name__ == "__main__":
    main()
