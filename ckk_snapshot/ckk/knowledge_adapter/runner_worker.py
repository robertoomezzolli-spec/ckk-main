"""Network-sealed worker for allowlisted CKK generator jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import time
from typing import Any


_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_PATHS = ("ckk_snapshot/ckk/gen/grammar.py", "ckk_snapshot/ckk/gen/expand.py")
_REPOSITORY = "https://github.com/robertoomezzolli-spec/ckk"
_OPERATOR = re.compile(r"^op_[a-z][a-z0-9_]{0,63}$")


def _validate(request: dict[str, Any]) -> None:
    expected = {
        "schema_version", "run_id", "repository", "commit_sha", "seed", "seed_hash",
        "operators", "controls", "compute_limits", "source_paths",
    }
    if set(request) != expected or request.get("schema_version") != 1:
        raise ValueError("invalid runner request schema")
    if not _RUN_ID.fullmatch(str(request["run_id"])) or not _SHA.fullmatch(str(request["commit_sha"])):
        raise ValueError("invalid pinned run identity")
    if request["repository"] != _REPOSITORY or tuple(request["source_paths"]) != _PATHS:
        raise ValueError("runner source is not allowlisted")
    seed = request["seed"]
    if not isinstance(seed, str) or not seed or len(seed) > 128:
        raise ValueError("invalid seed selector")
    if request["seed_hash"] != hashlib.sha256(seed.encode()).hexdigest():
        raise ValueError("seed provenance hash mismatch")
    operators = request["operators"]
    if not isinstance(operators, list) or len(operators) > 16 or any(not _OPERATOR.fullmatch(str(item)) for item in operators):
        raise ValueError("invalid operator allowlist")
    if request["controls"] not in (["structural_identity"], ["historical_identity"]):
        raise ValueError("invalid identity control")
    limits = request["compute_limits"]
    if set(limits) != {"levels", "state_cap", "derivation_cap", "wall_seconds", "memory_mb"}:
        raise ValueError("invalid compute limit schema")
    values = tuple(limits[name] for name in ("levels", "state_cap", "derivation_cap", "wall_seconds", "memory_mb"))
    if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
        raise ValueError("compute limits must be integers")
    if not (0 <= limits["levels"] <= 3 and 8 <= limits["state_cap"] <= 5000
            and 100 <= limits["derivation_cap"] <= 100000 and 2 <= limits["wall_seconds"] <= 45
            and 128 <= limits["memory_mb"] <= 768):
        raise ValueError("compute limits are outside sealed bounds")


def _git_blob(mirror: Path, commit_sha: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "--git-dir", str(mirror), "show", f"{commit_sha}:{path}"],
        capture_output=True, check=False, timeout=30,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    if result.returncode:
        raise RuntimeError("pinned CKK source blob is unavailable")
    return result.stdout


def _limits(memory_mb: int, wall_seconds: int):
    def apply() -> None:
        memory = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (wall_seconds, wall_seconds + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
    return apply


def _run(request: dict[str, Any], mirror: Path, artifacts: Path) -> dict[str, Any]:
    _validate(request)
    run_id = request["run_id"]
    artifact = artifacts / run_id
    artifact.mkdir(parents=True, exist_ok=False)
    (artifact / "request.json").write_text(json.dumps(request, sort_keys=True), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix=f"ckk-{run_id[:8]}-") as temporary:
        source = Path(temporary) / "source"
        source.mkdir()
        for path in _PATHS:
            (source / Path(path).name).write_bytes(_git_blob(mirror, request["commit_sha"], path))
        result_path = artifact / "result.json"
        limits = request["compute_limits"]
        process = subprocess.run(
            [sys.executable, "/app/ckk_snapshot/ckk/knowledge_adapter/execute_run.py",
             str(artifact / "request.json"), str(source), str(result_path)],
            capture_output=True, check=False, timeout=limits["wall_seconds"] + 2,
            preexec_fn=_limits(limits["memory_mb"], limits["wall_seconds"]),
            env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
        )
        if process.returncode:
            error = process.stderr.decode("utf-8", "replace")[-1000:]
            raise RuntimeError(f"sealed generator failed exit={process.returncode}: {error}")
        return json.loads(result_path.read_text(encoding="utf-8"))


def _write_result(results: Path, run_id: str, payload: dict[str, Any]) -> None:
    temporary = results / f".{run_id}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, results / f"{run_id}.json")


def work(queue: Path, mirror: Path, artifacts: Path) -> None:
    requests, running, results = queue / "requests", queue / "running", queue / "results"
    for path in (requests, running, results, artifacts):
        path.mkdir(parents=True, exist_ok=True)
    heartbeat = queue / "runner.heartbeat"
    while True:
        heartbeat.touch()
        for request_path in sorted(requests.glob("*.json")):
            if not _RUN_ID.fullmatch(request_path.stem):
                continue
            claimed = running / request_path.name
            try:
                os.replace(request_path, claimed)
            except FileNotFoundError:
                continue
            run_id = claimed.stem
            try:
                request = json.loads(claimed.read_text(encoding="utf-8"))
                payload = _run(request, mirror, artifacts)
            except Exception as exc:
                commit = request.get("commit_sha", "") if isinstance(locals().get("request"), dict) else ""
                payload = {
                    "schema_version": 1, "status": "failed", "run_id": run_id,
                    "commit_sha": commit, "error_type": type(exc).__name__, "error": str(exc)[:1200],
                }
            _write_result(results, run_id, payload)
            claimed.unlink(missing_ok=True)
        time.sleep(0.1)


def healthy(queue: Path) -> bool:
    heartbeat = queue / "runner.heartbeat"
    return heartbeat.is_file() and time.time() - heartbeat.stat().st_mtime < 15


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="/jobs")
    parser.add_argument("--mirror", default="/source-cache/repository.git")
    parser.add_argument("--artifacts", default="/artifacts")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if args.health:
        raise SystemExit(0 if healthy(Path(args.queue)) else 1)
    work(Path(args.queue), Path(args.mirror), Path(args.artifacts))


if __name__ == "__main__":
    main()
