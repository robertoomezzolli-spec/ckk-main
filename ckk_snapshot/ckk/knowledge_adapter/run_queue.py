"""Validated file-queue client for the network-sealed CKK generator runner."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
from typing import Any

from .index import GitMirror


REPOSITORY = "https://github.com/robertoomezzolli-spec/ckk"
_OPERATOR = re.compile(r"^op_[a-z][a-z0-9_]{0,63}$")
_CONTROL = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class RunBudgets:
    levels: int = 1
    state_cap: int = 400
    derivation_cap: int = 20000
    wall_seconds: int = 20
    memory_mb: int = 384

    @classmethod
    def validated(cls, raw: dict[str, Any] | None) -> "RunBudgets":
        raw = raw or {}
        if not set(raw).issubset({"levels", "state_cap", "derivation_cap", "wall_seconds", "memory_mb"}):
            raise ValueError("unsupported compute budget field")
        values = cls(
            levels=int(raw.get("levels", 1)),
            state_cap=int(raw.get("state_cap", 400)),
            derivation_cap=int(raw.get("derivation_cap", 20000)),
            wall_seconds=int(raw.get("wall_seconds", 20)),
            memory_mb=int(raw.get("memory_mb", 384)),
        )
        if not 0 <= values.levels <= 3:
            raise ValueError("levels must be between 0 and 3")
        if not 8 <= values.state_cap <= 5000:
            raise ValueError("state_cap must be between 8 and 5000")
        if not 100 <= values.derivation_cap <= 100000:
            raise ValueError("derivation_cap must be between 100 and 100000")
        if not 2 <= values.wall_seconds <= 45:
            raise ValueError("wall_seconds must be between 2 and 45")
        if not 128 <= values.memory_mb <= 768:
            raise ValueError("memory_mb must be between 128 and 768")
        return values


class CKKRunQueue:
    """Submit allowlisted experiments to a runner with no network interface."""

    def __init__(self, mirror: GitMirror, queue_directory: str | Path):
        self.mirror = mirror
        self.queue_directory = Path(queue_directory)

    def run(
        self,
        seed: str,
        operators: list[str] | None = None,
        controls: list[str] | None = None,
        budgets: dict[str, Any] | None = None,
        ref: str | None = None,
    ) -> dict[str, Any]:
        seed = str(seed).strip()
        if not seed or len(seed) > 128 or any(ord(char) < 32 for char in seed):
            raise ValueError("invalid seed selector")
        operators = [str(item).strip() for item in (operators or [])]
        if len(operators) > 16 or any(not _OPERATOR.fullmatch(item) for item in operators):
            raise ValueError("invalid operator allowlist")
        controls = [str(item).strip() for item in (controls or ["structural_identity"])]
        if not controls or len(controls) > 8 or any(not _CONTROL.fullmatch(item) for item in controls):
            raise ValueError("invalid controls")
        if not set(controls).issubset({"structural_identity", "historical_identity"}):
            raise ValueError("unsupported control")
        if len(set(controls)) != 1:
            raise ValueError("select exactly one identity control")
        compute = RunBudgets.validated(budgets)
        commit_sha = self.mirror.resolve(ref)
        run_id = uuid.uuid4().hex
        request = {
            "schema_version": 1,
            "run_id": run_id,
            "repository": REPOSITORY,
            "commit_sha": commit_sha,
            "seed": seed,
            "seed_hash": hashlib.sha256(seed.encode()).hexdigest(),
            "operators": operators,
            "controls": controls,
            "compute_limits": {
                "levels": compute.levels,
                "state_cap": compute.state_cap,
                "derivation_cap": compute.derivation_cap,
                "wall_seconds": compute.wall_seconds,
                "memory_mb": compute.memory_mb,
            },
            "source_paths": ["ckk_snapshot/ckk/gen/grammar.py", "ckk_snapshot/ckk/gen/expand.py"],
        }
        requests = self.queue_directory / "requests"
        results = self.queue_directory / "results"
        requests.mkdir(parents=True, exist_ok=True)
        results.mkdir(parents=True, exist_ok=True)
        temporary = requests / f".{run_id}.{os.getpid()}.tmp"
        target = requests / f"{run_id}.json"
        temporary.write_text(json.dumps(request, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, target)
        result_path = results / f"{run_id}.json"
        deadline = time.monotonic() + compute.wall_seconds + 15
        while time.monotonic() < deadline:
            if result_path.is_file():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if result.get("run_id") != run_id or result.get("commit_sha") != commit_sha:
                    raise RuntimeError("runner returned mismatched provenance")
                return result
            time.sleep(0.1)
        raise TimeoutError("sealed CKK runner did not return before deadline")
