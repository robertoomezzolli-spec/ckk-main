"""Online SQLite backups for the persistent organism identity volume."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time


def backup_once(database: Path, destination: Path, retain: int = 28) -> Path:
    if retain < 2:
        raise ValueError("retain must preserve at least two recovery points")
    if not database.is_file():
        raise FileNotFoundError(database)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"sovereign-{stamp}.sqlite3"
    with sqlite3.connect(database) as source, sqlite3.connect(target) as backup:
        source.backup(backup)
        result = backup.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RuntimeError("backup integrity check failed")
    snapshots = sorted(destination.glob("sovereign-*.sqlite3"), reverse=True)
    for expired in snapshots[retain:]:
        expired.unlink()
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("/data/sovereign.sqlite3"))
    parser.add_argument("--destination", type=Path, default=Path("/data/backups"))
    parser.add_argument("--retain", type=int, default=28)
    parser.add_argument("--interval", type=int, default=21600)
    args = parser.parse_args()
    if args.interval < 300:
        raise SystemExit("backup interval must be at least 300 seconds")
    while True:
        try:
            backup_once(args.database, args.destination, args.retain)
        except FileNotFoundError:
            pass
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
