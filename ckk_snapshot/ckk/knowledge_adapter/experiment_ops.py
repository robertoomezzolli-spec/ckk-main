"""Sealed control plane for the frozen CKK long-running experiment.

The public methods accept structured operations only.  They never expose a
shell, arbitrary repository URL, arbitrary executable, or a writable source
checkout.  A separate networkless worker owns all child processes.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
import uuid
from typing import Any

from .index import GitMirror, _run_git


JOB_ID = re.compile(r"^[0-9a-f]{32}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATES = frozenset(
    {
        "COMPLETED", "FAILED", "FAILED_EQUIVALENCE", "STOPPED", "TIMED_OUT", "MEMORY_LIMIT",
        "OOM_KILLED", "INTERRUPTED",
    }
)
TASKS = frozenset({"supervisor_smoke", "equivalence_validation", "fresh_seed_closure_plateau_v2"})
OPERATIONAL_LIMITS: dict[str, dict[str, int]] = {
    "supervisor_smoke": {
        "wall_seconds": 60,
        "cpu_seconds": 45,
        "memory_mb": 256,
        "file_size_mb": 32,
        "processes": 8,
    },
    "equivalence_validation": {
        "wall_seconds": 1800,
        "cpu_seconds": 1740,
        "memory_mb": 768,
        "file_size_mb": 128,
        "processes": 16,
    },
    "fresh_seed_closure_plateau_v2": {
        "wall_seconds": 14400,
        "cpu_seconds": 13800,
        "memory_mb": 1024,
        "file_size_mb": 512,
        "processes": 16,
    },
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(_canonical(value))
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


@dataclass(frozen=True)
class ExperimentSettings:
    repository_url: str
    branch: str
    target_commit: str
    cache_directory: str
    control_directory: str
    artifact_directory: str
    manifest_path: str


class ExperimentOperations:
    """Read-only Git access plus an asynchronous allowlisted process queue."""

    def __init__(self, settings: ExperimentSettings, mirror: GitMirror | None = None):
        self.settings = settings
        self.mirror = mirror or GitMirror(
            settings.repository_url,
            Path(settings.cache_directory) / "repository.git",
            settings.branch,
        )
        self.control = Path(settings.control_directory)
        self.artifacts = Path(settings.artifact_directory)
        self.manifest_path = Path(settings.manifest_path)
        self.control.mkdir(parents=True, exist_ok=True)
        for name in ("requests", "running", "status", "stop"):
            (self.control / name).mkdir(exist_ok=True)
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self._load_manifest()

    @property
    def repository(self) -> str:
        return self.mirror.canonical_repository

    def _load_manifest(self) -> tuple[dict[str, Any], bytes, str]:
        raw = self.manifest_path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise ValueError("invalid frozen experiment manifest")
        expected = {
            "repository": self.repository,
            "branch": self.settings.branch,
            "target_commit": self.settings.target_commit,
        }
        for field, value in expected.items():
            if manifest.get(field) != value:
                raise ValueError(f"frozen manifest {field} does not match configured experiment")
        if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("target_commit", ""))):
            raise ValueError("frozen manifest has no full target commit")
        statement = (
            "No hypothesis, threshold, horizon, initial condition, null, permutation count, "
            "or inclusion rule may be changed after execution begins."
        )
        if manifest.get("freeze_statement") != statement:
            raise ValueError("frozen manifest statement is missing or changed")
        return manifest, raw, hashlib.sha256(raw).hexdigest()

    def refresh(self) -> dict[str, Any]:
        branch_head = self.mirror.refresh()
        target = self.mirror.resolve(self.settings.target_commit)
        merge_base = _run_git(self.mirror.path, "merge-base", target, branch_head).strip()
        if merge_base != target:
            raise RuntimeError("frozen target commit is not reachable from configured branch")
        return {
            "status": "ready",
            "operation": "sync",
            "repository": self.repository,
            "branch": self.settings.branch,
            "branch_head": branch_head,
            "target_commit": target,
            "target_reachable_from_branch": True,
            "push_url": "disabled://read-only",
            "upstream_write_allowed": False,
            "belief_status": "not_committed",
        }

    def manifest(self) -> dict[str, Any]:
        manifest, _raw, digest = self._load_manifest()
        target = self.mirror.resolve(self.settings.target_commit)
        checks: list[dict[str, Any]] = []
        for item in manifest.get("source_files", []):
            path = str(item.get("path", ""))
            expected = str(item.get("sha256", ""))
            actual = str(self.mirror.read_path(path, target, maximum_chars=1)["content_sha256"])
            checks.append({"path": path, "expected_sha256": expected, "actual_sha256": actual, "matches": actual == expected})
        verified = bool(checks) and all(item["matches"] for item in checks)
        return {
            "status": "verified" if verified else "FAILED",
            "operation": "manifest",
            "repository": self.repository,
            "branch": self.settings.branch,
            "commit_sha": target,
            "manifest": manifest,
            "manifest_path": self.manifest_path.name,
            "manifest_sha256": digest,
            "source_verification": checks,
            "immutable_in_container": True,
            "upstream_write_allowed": False,
            "belief_status": "not_committed",
        }

    def repo(
        self,
        operation: str,
        *,
        path: str | None = None,
        ref: str | None = None,
        base_ref: str | None = None,
        target_ref: str | None = None,
    ) -> dict[str, Any]:
        operation = str(operation)
        if operation == "sync":
            return self.refresh()
        if operation == "manifest":
            return self.manifest()
        if operation == "status":
            branch_head = self.mirror.resolve(self.settings.branch)
            selected = self._selected()
            return {
                "status": "ready",
                "operation": "status",
                "repository": self.repository,
                "branch": self.settings.branch,
                "branch_head": branch_head,
                "target_commit": self.mirror.resolve(self.settings.target_commit),
                "selected_commit": selected.get("commit_sha"),
                "selected_ref": selected.get("ref"),
                "working_tree": "none_bare_fetch_only_mirror",
                "clean": True,
                "push_url": "disabled://read-only",
                "upstream_write_allowed": False,
                "belief_status": "not_committed",
            }
        if operation == "checkout":
            chosen = ref or self.settings.target_commit
            commit = self.mirror.resolve(chosen)
            selection = {
                "schema_version": 1,
                "repository": self.repository,
                "ref": chosen,
                "commit_sha": commit,
                "selected_at": time.time(),
                "detached_execution": True,
            }
            _atomic_json(self.control / "selected.json", selection)
            return {
                "status": "selected",
                "operation": "checkout",
                **selection,
                "source_writable": False,
                "upstream_write_allowed": False,
                "belief_status": "not_committed",
            }
        if operation == "read":
            if not path:
                raise ValueError("repo read requires a path")
            result = self.mirror.read_path(path, ref or self.settings.target_commit)
            return {"status": "completed", "operation": "read", **result}
        if operation == "diff":
            if not base_ref or not target_ref:
                raise ValueError("repo diff requires base_ref and target_ref")
            result = self.mirror.diff(base_ref, target_ref, maximum_chars=24000)
            return {
                "status": "completed",
                "operation": "diff",
                "repository": self.repository,
                "base_commit_sha": self.mirror.resolve(base_ref),
                "commit_sha": self.mirror.resolve(target_ref),
                "items": result,
                "upstream_write_allowed": False,
                "belief_status": "not_committed",
            }
        raise ValueError("unsupported repository operation")

    def _selected(self) -> dict[str, Any]:
        path = self.control / "selected.json"
        return _read_json(path) if path.is_file() else {}

    def start(self, task: str, manifest_sha256: str) -> dict[str, Any]:
        if task not in TASKS:
            raise ValueError("task is not allowlisted")
        if not SHA256.fullmatch(str(manifest_sha256)):
            raise ValueError("invalid manifest SHA-256")
        verified = self.manifest()
        if verified["status"] != "verified" or manifest_sha256 != verified["manifest_sha256"]:
            raise PermissionError("frozen manifest verification failed")
        selected = self._selected()
        if selected.get("commit_sha") != self.settings.target_commit:
            raise PermissionError("select the exact frozen target commit before starting a job")
        if task == "fresh_seed_closure_plateau_v2" and not self._equivalence_passed(manifest_sha256):
            raise PermissionError("a completed matching equivalence validation is required before the full experiment")
        running = [item for item in self.status()["jobs"] if item.get("state") not in TERMINAL_STATES]
        if running:
            raise RuntimeError("one experiment job is already queued or running")
        job_id = uuid.uuid4().hex
        now = time.time()
        request = {
            "schema_version": 1,
            "job_id": job_id,
            "task": task,
            "repository": self.repository,
            "branch": self.settings.branch,
            "commit_sha": self.settings.target_commit,
            "manifest_sha256": manifest_sha256,
            "requested_at": now,
            "operational_compute_limits": dict(OPERATIONAL_LIMITS[task]),
        }
        status = {
            **request,
            "state": "QUEUED",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "termination_class": None,
            "artifact_paths": [],
            "artifact_hashes": {},
        }
        _atomic_json(self.control / "status" / f"{job_id}.json", status)
        _atomic_json(self.control / "requests" / f"{job_id}.json", request)
        return {
            "status": "queued",
            "job_id": job_id,
            "task": task,
            "repository": self.repository,
            "commit_sha": self.settings.target_commit,
            "manifest_sha256": manifest_sha256,
            "operational_compute_limits": dict(OPERATIONAL_LIMITS[task]),
            "artifact_root": job_id,
            "belief_status": "not_committed",
        }

    def _equivalence_passed(self, manifest_sha256: str) -> bool:
        for path in (self.control / "status").glob("*.json"):
            try:
                status = _read_json(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if (
                status.get("task") == "equivalence_validation"
                and status.get("state") == "COMPLETED"
                and status.get("equivalence_passed") is True
                and status.get("commit_sha") == self.settings.target_commit
                and status.get("manifest_sha256") == manifest_sha256
            ):
                return True
        return False

    def status(self, job_id: str | None = None) -> dict[str, Any]:
        if job_id is not None:
            if not JOB_ID.fullmatch(str(job_id)):
                raise ValueError("invalid job ID")
            path = self.control / "status" / f"{job_id}.json"
            if not path.is_file():
                raise FileNotFoundError("experiment job does not exist")
            status = _read_json(path)
            return {"status": "completed", "job": status, "belief_status": "not_committed"}
        jobs: list[dict[str, Any]] = []
        for path in sorted((self.control / "status").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
            try:
                jobs.append(_read_json(path))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return {"status": "completed", "jobs": jobs, "belief_status": "not_committed"}

    def stop(self, job_id: str) -> dict[str, Any]:
        current = self.status(job_id)["job"]
        if current.get("state") in TERMINAL_STATES:
            return {
                "status": "already_terminal",
                "job_id": job_id,
                "state": current.get("state"),
                "belief_status": "not_committed",
            }
        marker = {"job_id": job_id, "requested_at": time.time(), "reason": "requested_by_kairos_capability"}
        _atomic_json(self.control / "stop" / f"{job_id}.json", marker)
        return {"status": "stop_requested", **marker, "belief_status": "not_committed"}

    def _artifact_path(self, raw_path: str) -> Path:
        candidate = PurePosixPath(str(raw_path).strip())
        if not raw_path or candidate.is_absolute() or ".." in candidate.parts or len(candidate.parts) < 2:
            raise ValueError("invalid artifact path")
        if not JOB_ID.fullmatch(candidate.parts[0]):
            raise ValueError("artifact path must begin with a valid job ID")
        cursor = self.artifacts
        for part in candidate.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise PermissionError("artifact symlinks are not readable")
        target = cursor
        if not target.is_file():
            raise FileNotFoundError("artifact does not exist")
        resolved = target.resolve()
        if not resolved.is_relative_to(self.artifacts.resolve()):
            raise PermissionError("artifact path escapes sealed storage")
        return resolved

    def file_read(self, path: str, offset: int = 0, maximum_chars: int = 24000) -> dict[str, Any]:
        target = self._artifact_path(path)
        offset = max(0, int(offset))
        maximum_chars = max(1, min(int(maximum_chars), 32000))
        size = target.stat().st_size
        with target.open("rb") as stream:
            stream.seek(offset)
            raw = stream.read(maximum_chars * 4)
        if b"\0" in raw[:8192]:
            raise ValueError("binary artifact is not readable as text")
        content = raw.decode("utf-8", "replace")
        excerpt = content[:maximum_chars]
        return {
            "status": "completed",
            "path": path,
            "offset": offset,
            "excerpt": excerpt,
            "truncated": offset + len(raw) < size or len(excerpt) < len(content),
            "size_bytes": size,
            "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
            "belief_status": "not_committed",
        }

    def file_hash(self, path: str) -> dict[str, Any]:
        target = self._artifact_path(path)
        digest = hashlib.sha256()
        size = 0
        with target.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        return {
            "status": "completed",
            "path": path,
            "algorithm": "sha256",
            "sha256": digest.hexdigest(),
            "size_bytes": size,
            "belief_status": "not_committed",
        }

    def metrics(self, job_id: str | None = None) -> dict[str, Any]:
        worker_path = self.control / "worker_metrics.json"
        worker = _read_json(worker_path) if worker_path.is_file() else {"status": "unavailable"}
        disk = os.statvfs(self.artifacts)
        payload: dict[str, Any] = {
            "status": "completed",
            "worker": worker,
            "artifact_disk": {
                "total_bytes": disk.f_blocks * disk.f_frsize,
                "available_bytes": disk.f_bavail * disk.f_frsize,
                "used_bytes": (disk.f_blocks - disk.f_bfree) * disk.f_frsize,
            },
            "kernel_log_access": False,
            "oom_evidence": "worker cgroup memory.events deltas plus process exit signal",
            "belief_status": "not_committed",
        }
        if job_id is not None:
            payload["job"] = self.status(job_id)["job"]
        return payload

    def health(self) -> dict[str, Any]:
        metrics_path = self.control / "worker_metrics.json"
        worker_age = None
        if metrics_path.is_file():
            worker_age = max(0.0, time.time() - metrics_path.stat().st_mtime)
        return {
            "configured": True,
            "repository": self.repository,
            "branch": self.settings.branch,
            "target_commit": self.settings.target_commit,
            "manifest_path": self.manifest_path.name,
            "worker_heartbeat_age_seconds": worker_age,
            "worker_ready": worker_age is not None and worker_age < 20,
            "upstream_write_allowed": False,
        }
