"""Persistent networkless supervisor for allowlisted CKK experiment jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any

from .experiment_ops import (
    JOB_ID, OPERATIONAL_LIMITS, TASKS, TERMINAL_STATES, _atomic_json, _canonical, _read_json,
)


SHA = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_bytes(path: Path) -> int:
    total = 0
    for candidate in path.rglob("*"):
        try:
            if candidate.is_file() and not candidate.is_symlink():
                total += candidate.stat().st_size
        except FileNotFoundError:
            continue
    return total


def _cgroup() -> dict[str, Any]:
    root = Path("/sys/fs/cgroup")
    values: dict[str, Any] = {}
    for name in ("memory.current", "memory.max", "memory.peak", "memory.events", "cpu.stat"):
        path = root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if "\n" in text or " " in text:
            parsed: dict[str, int | str] = {}
            for line in text.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    parsed[parts[0]] = int(parts[1])
            values[name] = parsed or text
        else:
            values[name] = int(text) if text.isdigit() else text
    return values


def _proc(pid: int) -> dict[str, Any]:
    status: dict[str, str] = {}
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                status[key] = value.strip()
        fields = Path(f"/proc/{pid}/stat").read_text().split()
        ticks = os.sysconf("SC_CLK_TCK")
        cpu_seconds = (int(fields[13]) + int(fields[14])) / ticks
    except (FileNotFoundError, ProcessLookupError, IndexError, ValueError):
        return {"pid": pid, "available": False}

    def kib(name: str) -> int | None:
        value = status.get(name, "").split()
        return int(value[0]) * 1024 if value and value[0].isdigit() else None

    return {
        "pid": pid,
        "available": True,
        "process_state": status.get("State"),
        "rss_bytes": kib("VmRSS"),
        "peak_rss_bytes": kib("VmHWM"),
        "virtual_memory_bytes": kib("VmSize"),
        "threads": int(status["Threads"]) if status.get("Threads", "").isdigit() else None,
        "cpu_seconds": round(cpu_seconds, 6),
    }


def _limits(limits: dict[str, int]):
    def apply() -> None:
        memory = limits["memory_mb"] * 1024 * 1024
        file_size = limits["file_size_mb"] * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CPU, (limits["cpu_seconds"], limits["cpu_seconds"] + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (limits["processes"], limits["processes"]))
        os.umask(0o077)
    return apply


def _validate_request(request: dict[str, Any], manifest: dict[str, Any], manifest_sha256: str) -> None:
    expected = {
        "schema_version", "job_id", "task", "repository", "branch", "commit_sha",
        "manifest_sha256", "requested_at", "operational_compute_limits", "retry_of",
    }
    if set(request) != expected or request.get("schema_version") != 1:
        raise ValueError("invalid experiment job request")
    if not JOB_ID.fullmatch(str(request.get("job_id", ""))) or request.get("task") not in TASKS:
        raise ValueError("invalid experiment job identity")
    for field in ("repository", "branch", "target_commit"):
        request_field = "commit_sha" if field == "target_commit" else field
        if request.get(request_field) != manifest.get(field):
            raise ValueError(f"job request {request_field} does not match frozen manifest")
    if request.get("manifest_sha256") != manifest_sha256:
        raise ValueError("job request manifest hash mismatch")
    if not SHA.fullmatch(str(request.get("commit_sha", ""))):
        raise ValueError("job request has no full commit SHA")
    if request.get("retry_of") is not None and not JOB_ID.fullmatch(str(request["retry_of"])):
        raise ValueError("job request has invalid retry provenance")
    if request.get("operational_compute_limits") != OPERATIONAL_LIMITS[request["task"]]:
        raise ValueError("job request changed the fixed operational compute limits")


def _archive(mirror: Path, commit: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    process = subprocess.Popen(
        ["git", "--git-dir", str(mirror), "archive", "--format=tar", commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"},
    )
    assert process.stdout is not None
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if member.issym() or member.islnk():
                    raise PermissionError("repository symlinks are not executable in the sealed workspace")
                archive.extract(member, destination, filter="data")
    finally:
        process.stdout.close()
    error = (process.stderr.read() if process.stderr else b"").decode("utf-8", "replace")
    if process.wait(timeout=60):
        raise RuntimeError("unable to extract frozen Git tree: " + error[-500:])


def _verify_sources(source: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for item in manifest.get("source_files", []):
        path = str(item["path"])
        target = source.joinpath(*Path(path).parts)
        actual = _sha256(target)
        expected = str(item["sha256"])
        checks.append({"path": path, "expected_sha256": expected, "actual_sha256": actual, "matches": actual == expected})
    if not checks or not all(item["matches"] for item in checks):
        raise RuntimeError("frozen source hash verification failed")
    return checks


def _readonly_source(source: Path) -> None:
    results = source / "results"
    if not results.exists():
        results.mkdir(mode=0o750)
    for path in source.rglob("*"):
        if path.is_dir():
            path.chmod(0o550)
        elif path.is_file():
            path.chmod(0o440)
    source.chmod(0o550)
    results.chmod(0o750)


def _environment() -> dict[str, Any]:
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=False, timeout=30
    )
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "experiment_dependency_class": "standard_library_only",
        "installed_environment": sorted(line for line in freeze.stdout.splitlines() if line.strip()),
        "network": "disabled_by_container_network_mode_none",
    }


def _artifact_inventory(artifact: Path) -> tuple[list[str], dict[str, str]]:
    paths: list[str] = []
    hashes: dict[str, str] = {}
    for path in sorted(artifact.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name == "status.json":
            continue
        relative = str(path.relative_to(artifact.parent))
        paths.append(relative)
        hashes[relative] = _sha256(path)
    return paths, hashes


def _seal_artifact(artifact: Path) -> None:
    for path in artifact.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(0o440)
        elif path.is_dir():
            path.chmod(0o550)
    artifact.chmod(0o550)


class ExperimentWorker:
    def __init__(self, control: Path, mirror: Path, artifacts: Path, workspaces: Path, manifest_path: Path):
        self.control = control
        self.mirror = mirror
        self.artifacts = artifacts
        self.workspaces = workspaces
        self.manifest_path = manifest_path
        for path in (control / "requests", control / "running", control / "status", control / "stop", artifacts, workspaces):
            path.mkdir(parents=True, exist_ok=True)
        self.manifest_raw = manifest_path.read_bytes()
        self.manifest = json.loads(self.manifest_raw)
        self.manifest_sha256 = hashlib.sha256(self.manifest_raw).hexdigest()

    def recover_interrupted(self) -> None:
        for path in (self.control / "running").glob("*.json"):
            if not JOB_ID.fullmatch(path.stem):
                continue
            try:
                request = _read_json(path)
                status_path = self.control / "status" / path.name
                status = _read_json(status_path) if status_path.is_file() else request
                if status.get("state") not in TERMINAL_STATES:
                    status.update({
                        "state": "INTERRUPTED",
                        "finished_at": time.time(),
                        "exit_code": None,
                        "termination_class": "SUPERVISOR_RESTART",
                    })
                    _atomic_json(status_path, status)
            finally:
                path.unlink(missing_ok=True)

    def _worker_metrics(self, current_job: str | None = None) -> None:
        disk = os.statvfs(self.artifacts)
        payload = {
            "status": "ready",
            "updated_at": time.time(),
            "pid": os.getpid(),
            "load_average": list(os.getloadavg()),
            "cpu_count": os.cpu_count(),
            "current_job_id": current_job,
            "cgroup": _cgroup(),
            "artifact_disk": {
                "total_bytes": disk.f_blocks * disk.f_frsize,
                "available_bytes": disk.f_bavail * disk.f_frsize,
            },
        }
        _atomic_json(self.control / "worker_metrics.json", payload)

    def run_once(self) -> bool:
        requests = sorted((self.control / "requests").glob("*.json"))
        if not requests:
            self._worker_metrics()
            return False
        request_path = next((path for path in requests if JOB_ID.fullmatch(path.stem)), None)
        if request_path is None:
            self._worker_metrics()
            return False
        running_path = self.control / "running" / request_path.name
        try:
            os.replace(request_path, running_path)
        except FileNotFoundError:
            return False
        request = _read_json(running_path)
        self._run(request)
        running_path.unlink(missing_ok=True)
        return True

    def _run(self, request: dict[str, Any]) -> None:
        _validate_request(request, self.manifest, self.manifest_sha256)
        job_id, task = request["job_id"], request["task"]
        limits = request["operational_compute_limits"]
        status_path = self.control / "status" / f"{job_id}.json"
        artifact = self.artifacts / job_id
        workspace = self.workspaces / job_id
        artifact.mkdir(mode=0o750, exist_ok=False)
        started = time.time()
        status = {
            **request,
            "state": "PREPARING",
            "started_at": started,
            "finished_at": None,
            "exit_code": None,
            "termination_class": None,
            "artifact_paths": [],
            "artifact_hashes": {},
        }
        _atomic_json(status_path, status)
        (artifact / "request.json").write_bytes(_canonical(request))
        (artifact / "manifest.json").write_bytes(self.manifest_raw)
        (artifact / "manifest.sha256").write_text(self.manifest_sha256 + "  manifest.json\n", encoding="utf-8")
        stdout_path, stderr_path = artifact / "stdout.log", artifact / "stderr.log"
        cgroup_before = _cgroup()
        peak_rss = 0
        stop_requested = False
        timed_out = False
        try:
            source = workspace / "source"
            workspace.mkdir(mode=0o750, exist_ok=False)
            _archive(self.mirror, request["commit_sha"], source)
            checks = _verify_sources(source, self.manifest)
            _atomic_json(artifact / "source-verification.json", {"commit_sha": request["commit_sha"], "checks": checks})
            _atomic_json(artifact / "environment.json", _environment())
            _readonly_source(source)
            if task == "supervisor_smoke":
                command = [
                    sys.executable, "/app/ckk_snapshot/ckk/knowledge_adapter/experiment_driver.py", "smoke",
                    "--output", str(artifact / "smoke.json"),
                ]
            elif task == "equivalence_validation":
                command = [
                    sys.executable, "/app/ckk_snapshot/ckk/knowledge_adapter/experiment_driver.py", "equivalence",
                    "--source", str(source), "--output", str(artifact / "equivalence.json"),
                ]
            else:
                command = [sys.executable, str(source / self.manifest["experiment_entry_point"])]
            _atomic_json(artifact / "execution.json", {
                "task": task,
                "argv": [str(item) for item in command],
                "working_directory": str(source),
                "started_at": started,
                "operational_compute_limits": limits,
                "scientific_parameters_source": "manifest.json",
            })
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "PYTHONHASHSEED": "0",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            }
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(
                    command,
                    cwd=source,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=environment,
                    preexec_fn=_limits(limits),
                    start_new_session=True,
                )
                status.update({"state": "RUNNING", "pid": process.pid, "process_group": process.pid})
                _atomic_json(status_path, status)
                deadline = started + int(limits["wall_seconds"])
                while process.poll() is None:
                    current = _proc(process.pid)
                    peak_rss = max(peak_rss, int(current.get("peak_rss_bytes") or current.get("rss_bytes") or 0))
                    status.update({
                        "runtime_seconds": round(time.time() - started, 3),
                        "process": current,
                        "peak_rss_bytes": peak_rss,
                        "cgroup": _cgroup(),
                        "artifact_bytes": _tree_bytes(artifact),
                    })
                    _atomic_json(status_path, status)
                    self._worker_metrics(job_id)
                    if (self.control / "stop" / f"{job_id}.json").is_file():
                        stop_requested = True
                        try:
                            os.killpg(process.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        break
                    if time.time() >= deadline:
                        timed_out = True
                        try:
                            os.killpg(process.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        break
                    time.sleep(1)
                if stop_requested or timed_out:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                exit_code = process.wait()

            if task == "fresh_seed_closure_plateau_v2" and exit_code == 0:
                generated = source / "results" / "fresh_seed_closure_plateau_gate_v2.json"
                if not generated.is_file():
                    raise RuntimeError("scientific process exited zero without its frozen result artifact")
                shutil.copyfile(generated, artifact / "result.json")
            equivalence_passed = None
            if task == "equivalence_validation" and (artifact / "equivalence.json").is_file():
                equivalence_passed = _read_json(artifact / "equivalence.json").get("equivalence_passed") is True
            cgroup_after = _cgroup()
            before_events = cgroup_before.get("memory.events", {})
            after_events = cgroup_after.get("memory.events", {})
            oom_delta = (
                int(after_events.get("oom_kill", 0)) - int(before_events.get("oom_kill", 0))
                if isinstance(before_events, dict) and isinstance(after_events, dict) else 0
            )
            if stop_requested:
                state, termination = "STOPPED", "MANUAL_STOP"
            elif timed_out:
                state, termination = "TIMED_OUT", "COMPUTATIONAL_LIMIT_WALL_CLOCK"
            elif oom_delta > 0:
                state, termination = "OOM_KILLED", "COMPUTATIONAL_LIMIT_MEMORY"
            elif exit_code != 0 and stderr_path.is_file() and any(
                marker in stderr_path.read_text(encoding="utf-8", errors="replace")[-8192:]
                for marker in ("MemoryError", "Cannot allocate memory", "cannot allocate memory")
            ):
                state, termination = "MEMORY_LIMIT", "COMPUTATIONAL_LIMIT_ADDRESS_SPACE"
            elif task == "equivalence_validation" and not equivalence_passed:
                state, termination = "FAILED_EQUIVALENCE", "EQUIVALENCE_GATE_FAILED"
            elif exit_code != 0:
                state, termination = "FAILED", "PROCESS_EXIT_NONZERO"
            else:
                state, termination = "COMPLETED", "NORMAL_EXIT"
            status.update({
                "state": state,
                "finished_at": time.time(),
                "runtime_seconds": round(time.time() - started, 3),
                "exit_code": exit_code,
                "exit_signal": -exit_code if exit_code < 0 else None,
                "termination_class": termination,
                "equivalence_passed": equivalence_passed,
                "peak_rss_bytes": peak_rss,
                "cgroup_before": cgroup_before,
                "cgroup_after": cgroup_after,
                "oom_kill_delta": oom_delta,
            })
        except Exception as exc:
            status.update({
                "state": "FAILED",
                "finished_at": time.time(),
                "runtime_seconds": round(time.time() - started, 3),
                "exit_code": status.get("exit_code"),
                "termination_class": "SUPERVISOR_ERROR",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1200],
                "peak_rss_bytes": peak_rss,
            })
            stderr_path.write_text(f"{type(exc).__name__}: {str(exc)[:1200]}\n", encoding="utf-8")
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
            (self.control / "stop" / f"{job_id}.json").unlink(missing_ok=True)
            _atomic_json(artifact / "status.json", status)
            paths, hashes = _artifact_inventory(artifact)
            status["artifact_paths"], status["artifact_hashes"] = paths, hashes
            status["result_path"] = (
                f"{job_id}/result.json" if (artifact / "result.json").is_file()
                else f"{job_id}/equivalence.json" if (artifact / "equivalence.json").is_file()
                else None
            )
            status["result_sha256"] = hashes.get(status["result_path"] or "")
            _atomic_json(status_path, status)
            _atomic_json(artifact / "status.json", status)
            _seal_artifact(artifact)
            self._worker_metrics()

    def work(self) -> None:
        self.recover_interrupted()
        while True:
            if not self.run_once():
                time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", default="/experiment-control")
    parser.add_argument("--mirror", default="/experiment-cache/repository.git")
    parser.add_argument("--artifacts", default="/experiment-artifacts")
    parser.add_argument("--workspaces", default="/experiment-workspaces")
    parser.add_argument("--manifest", default="/app/sealed/fresh_seed_closure_plateau_v2_execution_manifest.json")
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if args.health:
        metrics = Path(args.control) / "worker_metrics.json"
        raise SystemExit(0 if metrics.is_file() and time.time() - metrics.stat().st_mtime < 20 else 1)
    worker = ExperimentWorker(
        Path(args.control), Path(args.mirror), Path(args.artifacts), Path(args.workspaces), Path(args.manifest)
    )
    worker.work()


if __name__ == "__main__":
    main()
