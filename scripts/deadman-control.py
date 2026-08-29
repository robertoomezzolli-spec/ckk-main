#!/usr/bin/env python3
"""Offline dead-man key and lease utility. Keep the private key off-host."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import secrets
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ckk.sovereign.deadman import ACTIVE_SECONDS, QUARANTINE_SECONDS, canonical_payload


def generate(private_path: Path, public_path: Path) -> None:
    if private_path.exists() or public_path.exists():
        raise SystemExit("refusing to overwrite an existing dead-man key")
    key = Ed25519PrivateKey.generate()
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def renew(private_path: Path, output_path: Path, issued_at: int) -> None:
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("dead-man private key is not Ed25519")
    payload = {
        "version": 1,
        "sequence": issued_at,
        "issued_at": issued_at,
        "restricted_at": issued_at + ACTIVE_SECONDS,
        "quarantine_at": issued_at + QUARANTINE_SECONDS,
        "nonce": secrets.token_hex(16),
    }
    signature = key.sign(canonical_payload(payload))
    output_path.write_text(
        json.dumps(
            {"payload": payload, "signature": base64.b64encode(signature).decode()},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    output_path.chmod(0o644)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("keygen")
    keygen.add_argument("--private", type=Path, required=True)
    keygen.add_argument("--public", type=Path, required=True)
    lease = sub.add_parser("renew")
    lease.add_argument("--private", type=Path, required=True)
    lease.add_argument("--output", type=Path, required=True)
    lease.add_argument("--issued-at", type=int, default=None)
    args = parser.parse_args()
    if args.command == "keygen":
        generate(args.private, args.public)
    else:
        renew(args.private, args.output, args.issued_at or int(time.time()))


if __name__ == "__main__":
    main()
