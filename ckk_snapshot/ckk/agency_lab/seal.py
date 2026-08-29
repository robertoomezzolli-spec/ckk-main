"""Source seal verification for the experiment fork."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[3]


def verify_seal(root: Path = DEFAULT_ROOT) -> dict:
    from .protocol import PROTOCOL

    manifest_path = root / "sealed" / "agency_lab_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("agency lab seal manifest is missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("protocol_hash") != PROTOCOL.protocol_hash:
        raise RuntimeError("agency protocol hash differs from preregistration")
    for item in manifest["files"]:
        path = root / item["path"]
        if not path.is_file():
            raise RuntimeError(f"sealed source is missing: {item['path']}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise RuntimeError(f"sealed source changed: {item['path']}")
    aggregate = hashlib.sha256(
        "".join(f"{item['path']}:{item['sha256']}\n" for item in manifest["files"]).encode()
    ).hexdigest()
    if aggregate != manifest["source_seal"]:
        raise RuntimeError("agency lab aggregate seal is invalid")
    return manifest
