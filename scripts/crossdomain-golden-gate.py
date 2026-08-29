#!/usr/bin/env python3
"""Fail-closed gate for the immutable cross-domain CKK research suite.

Partial historical records are inventoried, never promoted to executable fixtures.
This script reads files only; it does not modify grammar, graph, Neon, or production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "crossdomain"
MANIFEST = SUITE / "fixtures" / "manifest.json"
SUMS = SUITE / "SHA256SUMS.json"
REQUIRED = ("physics", "chemistry", "biology", "computation")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_manifest_path(value: str) -> Path:
    return (MANIFEST.parent / value).resolve()


def build_report() -> dict:
    manifest = load_json(MANIFEST)
    sums = load_json(SUMS)
    domains = manifest.get("domains", {})
    failures = []
    report = {
        "suite_version": manifest.get("suite_version"),
        "starting_commit": manifest.get("starting_commit"),
        "hashes": {"status": "PASS", "checked": 0, "failures": []},
        "domains": {},
    }

    for relative, expected in sums.get("files", {}).items():
        path = SUITE / relative
        actual = file_sha256(path) if path.is_file() else None
        report["hashes"]["checked"] += 1
        if actual != expected:
            detail = {"file": relative, "expected": expected, "actual": actual}
            report["hashes"]["failures"].append(detail)
            failures.append(f"hash mismatch: {relative}")
    if report["hashes"]["failures"]:
        report["hashes"]["status"] = "FAIL"

    for domain in REQUIRED:
        entry = domains.get(domain)
        if not entry:
            failures.append(f"{domain}: missing manifest entry")
            continue
        row = {"archive_status": entry.get("status")}
        documents = {}
        invalid = False
        for key in ("seed_fixture", "expected_structural", "holdouts", "metadata"):
            value = entry.get(key)
            path = resolve_manifest_path(value) if value else None
            if not path or not path.is_file() or SUITE not in path.parents:
                failures.append(f"{domain}: invalid or missing {key}")
                invalid = True
                continue
            document = load_json(path)
            if document.get("domain") != domain:
                failures.append(f"{domain}: {key} domain mismatch")
                invalid = True
            documents[key] = document

        if invalid:
            row["gate"] = "INVALID"
            report["domains"][domain] = row
            continue

        seed = documents["seed_fixture"]
        expected = documents["expected_structural"]
        holdouts = documents["holdouts"]
        executable = seed.get("executable") is True and isinstance(seed.get("seeds"), list)
        outputs_frozen = isinstance(expected.get("expected_structural_signatures"), list)
        events_frozen = isinstance(expected.get("expected_derivation_events"), list)
        holdouts_frozen = isinstance(holdouts.get("holdouts"), list)
        row.update({
            "executable_seed_fixture": executable,
            "seed_count": len(seed.get("seeds") or []),
            "expected_structural_frozen": outputs_frozen,
            "expected_derivations_frozen": events_frozen,
            "holdouts_frozen": holdouts_frozen,
        })
        ready = executable and outputs_frozen and events_frozen and holdouts_frozen
        row["gate"] = "READY" if ready else "BLOCKED"
        if not ready:
            missing = []
            if not executable:
                missing.append("EXECUTABLE_SEED_FIXTURE")
            if not outputs_frozen or not events_frozen:
                missing.append("FROZEN_EXPECTED_OUTPUT")
            if not holdouts_frozen:
                missing.append("INDEPENDENT_HOLDOUT_FIXTURE")
            row["blocking_reasons"] = missing
            failures.extend(f"{domain}: missing {item}" for item in missing)
        report["domains"][domain] = row

    report["result"] = "PASS" if not failures else "FAIL"
    report["failures"] = failures
    return report


def audit(allow_incomplete: bool = False) -> int:
    report = build_report()
    if allow_incomplete and report["result"] == "FAIL":
        report["result"] = "INCOMPLETE_ALLOWED"
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["failures"] and not allow_incomplete:
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-incomplete", action="store_true", help="inventory only; never use this mode to certify regression PASS")
    args = parser.parse_args()
    sys.exit(audit(args.allow_incomplete))
