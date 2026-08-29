#!/usr/bin/env python3
"""Intentionally reseal the Agency Lab after reviewed source changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ckk_snapshot"))
from ckk.agency_lab.protocol import PROTOCOL  # noqa: E402


FILES = (
    "ckk_snapshot/ckk/agency_lab/__init__.py",
    "ckk_snapshot/ckk/agency_lab/brain.py",
    "ckk_snapshot/ckk/agency_lab/cli.py",
    "ckk_snapshot/ckk/agency_lab/harness.py",
    "ckk_snapshot/ckk/agency_lab/model.py",
    "ckk_snapshot/ckk/agency_lab/protocol.py",
    "ckk_snapshot/ckk/agency_lab/runner.py",
    "ckk_snapshot/ckk/agency_lab/seal.py",
    "ckk_snapshot/ckk/agency_lab/world.py",
)


def main() -> None:
    files = [{"path": name, "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name in FILES]
    source_seal = hashlib.sha256(
        "".join(f"{item['path']}:{item['sha256']}\n" for item in files).encode()
    ).hexdigest()
    manifest = {
        "schema": "ckk-agency-lab-seal-v1",
        "protocol_hash": PROTOCOL.protocol_hash,
        "source_seal": source_seal,
        "files": files,
    }
    destination = ROOT / "sealed" / "agency_lab_manifest.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
