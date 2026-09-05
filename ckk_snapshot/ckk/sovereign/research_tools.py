"""Sealed production tool registry for CKK evidence and deferred WhatsApp output."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Callable

from .knowledge import CKKKnowledgeClient


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


CKK_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "ckk",
    "description": (
        "Read-only CKK research evidence. Results are external evidence, not committed beliefs. "
        "Every result is pinned to a canonical Git commit and carries provenance."
    ),
    "tools": [
        {
            "type": "function", "name": "search", "strict": True,
            "description": "Logical capability ckk.search: search canonical CKK code/docs/audits/snapshots at the indexed commit.",
            "parameters": _object({
                "query": {"type": "string", "description": "Exact symbol, filename, text, or semantic query."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                "mode": {"type": "string", "enum": ["hybrid", "exact", "semantic", "symbol", "filename"]},
            }, ["query", "limit", "mode"]),
        },
        {
            "type": "function", "name": "read", "strict": True,
            "description": "Logical capability ckk.read: read one discovered repository path, optionally at an explicit ref.",
            "parameters": _object({
                "path": {"type": "string", "description": "Repository-relative path returned by CKK search/symbol."},
                "ref": {"type": ["string", "null"], "description": "Commit SHA or safe Git ref; null pins current canonical ref."},
            }, ["path", "ref"]),
        },
        {
            "type": "function", "name": "symbol", "strict": True,
            "description": "Logical capability ckk.symbol: exact code-symbol lookup in the canonical indexed snapshot.",
            "parameters": _object({
                "name": {"type": "string", "description": "Exact identifier such as op_winding."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            }, ["name", "limit"]),
        },
        {
            "type": "function", "name": "run", "strict": True,
            "description": (
                "Logical capability ckk.run: run the pinned repository's real grammar.py/expand.py in a network-sealed "
                "sandbox. Use a canonical seed selector (SEED_R, SEEDS, numeric index, or exact seed label)."
            ),
            "parameters": _object({
                "seed": {"type": "string"},
                "operators": {"type": "array", "items": {"type": "string"}, "maxItems": 16},
                "controls": {
                    "type": "array", "items": {"type": "string", "enum": ["structural_identity", "historical_identity"]},
                    "minItems": 1, "maxItems": 1,
                },
                "budgets": _object({
                    "levels": {"type": "integer", "minimum": 0, "maximum": 3},
                    "state_cap": {"type": "integer", "minimum": 8, "maximum": 5000},
                    "derivation_cap": {"type": "integer", "minimum": 100, "maximum": 100000},
                    "wall_seconds": {"type": "integer", "minimum": 2, "maximum": 45},
                    "memory_mb": {"type": "integer", "minimum": 128, "maximum": 768},
                }, ["levels", "state_cap", "derivation_cap", "wall_seconds", "memory_mb"]),
                "ref": {"type": ["string", "null"]},
            }, ["seed", "operators", "controls", "budgets", "ref"]),
        },
    ],
}

WHATSAPP_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "whatsapp",
    "description": "Policy-gated WhatsApp output capability. Tool calls only propose output; the runtime actuator remains authoritative.",
    "tools": [{
        "type": "function", "name": "send", "strict": True,
        "description": "Logical capability whatsapp.send. Propose a reply; trusted runtime policy performs any real send after cognition.",
        "parameters": _object({"text": {"type": "string"}}, ["text"]),
    }],
}

RESEARCH_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "research",
    "description": (
        "Sealed publisher for an existing completed CKK run. It cannot edit arbitrary web content and publishes "
        "only validated run artifacts with provenance. Publishing does not commit evidence as belief."
    ),
    "tools": [{
        "type": "function", "name": "publish", "strict": True,
        "description": "Logical capability research.publish: publish one completed CKK run by exact run ID.",
        "parameters": _object({"run_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"}}, ["run_id"]),
    }],
}

REPO_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "repo",
    "description": (
        "Read-only operations for the one allowlisted frozen ckk-main experiment repository. "
        "No remote writes, pushes, arbitrary repository URLs, or writable source checkout are available."
    ),
    "tools": [{
        "type": "function", "name": "read", "strict": True,
        "description": (
            "Logical capability repo.read. Structured operations: sync the fixed mirror; select an exact ref; inspect "
            "status; read a repository path; inspect a bounded diff; or verify/read the frozen execution manifest."
        ),
        "parameters": _object({
            "operation": {"type": "string", "enum": ["sync", "checkout", "status", "read", "diff", "manifest"]},
            "path": {"type": ["string", "null"]},
            "ref": {"type": ["string", "null"]},
            "base_ref": {"type": ["string", "null"]},
            "target_ref": {"type": ["string", "null"]},
        }, ["operation", "path", "ref", "base_ref", "target_ref"]),
    }],
}

PROCESS_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "process",
    "description": (
        "Persistent sealed supervisor for the frozen CKK experiment. Jobs outlive a model interaction. "
        "Only fixed task identifiers are executable; there is no shell or arbitrary command parameter."
    ),
    "tools": [
        {
            "type": "function", "name": "run", "strict": True,
            "description": (
                "Logical capability process.run. Queue a supervisor smoke test, the mandatory brute-force "
                "equivalence validation, or the frozen full experiment. Full execution is rejected until matching "
                "equivalence evidence exists. Jobs are persistent and completion is delivered as a later ordinary "
                "status event. Call once, then return a short acknowledgement; do not poll in the same WAKE."
            ),
            "parameters": _object({
                "task": {"type": "string", "enum": [
                    "supervisor_smoke", "equivalence_validation", "fresh_seed_closure_plateau_v2"
                ]},
                "manifest_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "retry_of": {
                    "type": ["string", "null"], "pattern": "^[0-9a-f]{32}$",
                    "description": "A matching failed job ID only when explicitly retrying; otherwise null.",
                },
            }, ["task", "manifest_sha256", "retry_of"]),
        },
        {
            "type": "function", "name": "status", "strict": True,
            "description": (
                "Logical capability process.status. Read one job or the recent job list and explicit termination "
                "class. For a running persistent job, inspect once and return to the user; never busy-poll in one WAKE."
            ),
            "parameters": _object({"job_id": {"type": ["string", "null"], "pattern": "^[0-9a-f]{32}$"}}, ["job_id"]),
        },
        {
            "type": "function", "name": "stop", "strict": True,
            "description": "Logical capability process.stop. Gracefully stop only a job created by this sealed supervisor.",
            "parameters": _object({"job_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"}}, ["job_id"]),
        },
    ],
}

FILE_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "file",
    "description": "Read-only access to generated experiment artifacts by job-relative path. No general filesystem access.",
    "tools": [
        {
            "type": "function", "name": "read", "strict": True,
            "description": "Logical capability file.read. Read a bounded text excerpt from a sealed job artifact.",
            "parameters": _object({
                "path": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "maximum_chars": {"type": "integer", "minimum": 1, "maximum": 32000},
            }, ["path", "offset", "maximum_chars"]),
        },
        {
            "type": "function", "name": "hash", "strict": True,
            "description": "Logical capability file.hash. Stream SHA-256 over one sealed job artifact.",
            "parameters": _object({"path": {"type": "string"}}, ["path"]),
        },
    ],
}

SYSTEM_NAMESPACE: dict[str, Any] = {
    "type": "namespace",
    "name": "system",
    "description": "Read-only CPU, memory, disk, runtime, exit and cgroup/OOM evidence for the sealed experiment worker.",
    "tools": [{
        "type": "function", "name": "metrics", "strict": True,
        "description": "Logical capability system.metrics. Observe worker resources and optionally one job; changes nothing.",
        "parameters": _object({"job_id": {"type": ["string", "null"], "pattern": "^[0-9a-f]{32}$"}}, ["job_id"]),
    }],
}


@dataclass
class SealedResearchToolRegistry:
    ckk: CKKKnowledgeClient
    audit_sink: Callable[[dict[str, Any]], None] = lambda event: None
    job_binding_sink: Callable[[str, str], None] = lambda job_id, recipient: None
    invocations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def capabilities(self) -> tuple[str, ...]:
        return (
            "whatsapp.send", "ckk.search", "ckk.read", "ckk.symbol", "ckk.run", "research.publish",
            "repo.read", "process.run", "process.status", "process.stop", "file.read", "file.hash",
            "system.metrics",
        )

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return deepcopy([
            WHATSAPP_NAMESPACE, CKK_NAMESPACE, RESEARCH_NAMESPACE, REPO_NAMESPACE, PROCESS_NAMESPACE,
            FILE_NAMESPACE, SYSTEM_NAMESPACE,
        ])

    @property
    def definition_sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.definitions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def logical_name(name: str, namespace: str | None = None) -> str:
        aliases = {
            "ckk_search": "ckk.search", "ckk_read": "ckk.read", "ckk_symbol": "ckk.symbol", "ckk_run": "ckk.run",
            "whatsapp_send": "whatsapp.send", "research_publish": "research.publish",
            "repo_read": "repo.read", "process_run": "process.run", "process_status": "process.status",
            "process_stop": "process.stop", "file_read": "file.read", "file_hash": "file.hash",
            "system_metrics": "system.metrics",
        }
        if name in aliases:
            return aliases[name]
        if "." in name:
            return name
        if namespace in {"ckk", "whatsapp", "research", "repo", "process", "file", "system"}:
            return f"{namespace}.{name}"
        if name in {"search", "read", "symbol", "run"}:
            return f"ckk.{name}"
        if name == "send":
            return "whatsapp.send"
        if name == "publish":
            return "research.publish"
        if name == "metrics":
            return "system.metrics"
        if name == "hash":
            return "file.hash"
        if name in {"status", "stop"}:
            return f"process.{name}"
        return name

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        namespace: str | None = None,
        reply_to: str | None = None,
        service_available: bool = False,
    ) -> dict[str, Any]:
        logical = self.logical_name(name, namespace)
        started_monotonic = time.monotonic()
        started_at = time.time()
        try:
            if logical == "ckk.search":
                result = self.ckk.search(arguments["query"], limit=arguments["limit"], mode=arguments["mode"])
            elif logical == "ckk.read":
                result = self.ckk.read(arguments["path"], ref=arguments.get("ref"))
            elif logical == "ckk.symbol":
                result = self.ckk.symbol(arguments["name"], limit=arguments["limit"])
            elif logical == "ckk.run":
                result = self.ckk.run(
                    arguments["seed"], operators=arguments["operators"], controls=arguments["controls"],
                    budgets=arguments["budgets"], ref=arguments.get("ref"),
                )
            elif logical == "research.publish":
                result = self.ckk.publish(arguments["run_id"])
            elif logical == "repo.read":
                result = self.ckk.experiment_repo(
                    arguments["operation"], path=arguments.get("path"), ref=arguments.get("ref"),
                    base_ref=arguments.get("base_ref"), target_ref=arguments.get("target_ref"),
                )
            elif logical == "process.run":
                result = self.ckk.experiment_process_run(
                    arguments["task"], arguments["manifest_sha256"], arguments.get("retry_of")
                )
                if reply_to and result.get("job_id"):
                    self.job_binding_sink(str(result["job_id"]), reply_to)
                result = {
                    **result,
                    "persistent_job": True,
                    "completion_notification_scheduled": bool(reply_to and result.get("job_id")),
                    "same_wake_polling_prohibited": True,
                    "required_next_action": (
                        "Return a short service_message with the job ID and current state now. "
                        "Do not call process.status or system.metrics again in this WAKE; a completion event will arrive."
                    ),
                }
            elif logical == "process.status":
                result = self.ckk.experiment_process_status(arguments.get("job_id"))
                job = result.get("job") if isinstance(result.get("job"), dict) else {}
                if reply_to and job.get("job_id"):
                    self.job_binding_sink(str(job["job_id"]), reply_to)
                if job.get("state") not in {"COMPLETED", "FAILED", "FAILED_EQUIVALENCE", "STOPPED", "TIMED_OUT", "MEMORY_LIMIT", "OOM_KILLED", "INTERRUPTED"}:
                    result = {
                        **result,
                        "same_wake_polling_prohibited": True,
                        "required_next_action": (
                            "Return the current persistent job state to the user now. Do not poll again in this WAKE; "
                            "a completion event will arrive."
                        ),
                    }
            elif logical == "process.stop":
                result = self.ckk.experiment_process_stop(arguments["job_id"])
            elif logical == "file.read":
                result = self.ckk.experiment_file_read(
                    arguments["path"], arguments["offset"], arguments["maximum_chars"]
                )
            elif logical == "file.hash":
                result = self.ckk.experiment_file_hash(arguments["path"])
            elif logical == "system.metrics":
                result = self.ckk.experiment_system_metrics(arguments.get("job_id"))
            elif logical == "whatsapp.send":
                if not reply_to or not service_available:
                    raise PermissionError("whatsapp.send unavailable outside an admitted service window")
                result = {
                    "status": "deferred_to_runtime_policy", "recipient_bound": True,
                    "instruction": "Return the text as a service_message in the final structured decision.",
                }
            else:
                raise PermissionError("tool is not registered in the sealed capability allowlist")
        except Exception as exc:
            failed_result = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:500]}
            self._record_event(logical, arguments, failed_result, started_at, started_monotonic)
            raise
        context_result = self._bounded_for_model(logical, result)
        self._record_event(logical, arguments, result, started_at, started_monotonic)
        return context_result

    def _record_event(
        self,
        logical: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        started_at: float,
        started_monotonic: float,
    ) -> None:
        job = result.get("job") if isinstance(result.get("job"), dict) else {}
        event = {
            "logical_name": logical,
            "argument_summary": self._argument_summary(logical, arguments),
            "arguments_sha256": hashlib.sha256(json.dumps(arguments, sort_keys=True, default=str).encode()).hexdigest(),
            "result_sha256": hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest(),
            "repository": result.get("repository") or job.get("repository"),
            "commit_sha": result.get("commit_sha") or job.get("commit_sha"),
            "run_id": result.get("run_id") if isinstance(result, dict) else None,
            "job_id": result.get("job_id") or job.get("job_id"),
            "operator_names": result.get("operator_names", []) if isinstance(result, dict) else [],
            "started_at": started_at,
            "finished_at": time.time(),
            "status": result.get("status") or job.get("state"),
            "exit_status": result.get("exit_code") if result.get("exit_code") is not None else job.get("exit_code"),
            "artifact_path": result.get("result_path") or job.get("result_path") or result.get("path"),
            "artifact_sha256": (
                result.get("result_sha256") or job.get("result_sha256")
                or result.get("sha256") or result.get("content_sha256")
            ),
            "latency_ms": round((time.monotonic() - started_monotonic) * 1000, 3),
            "belief_status": "not_committed",
        }
        self.invocations.append(event)
        self.invocations[:] = self.invocations[-100:]
        self.audit_sink(event)

    @staticmethod
    def _argument_summary(logical: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if logical == "ckk.search":
            return {"query": str(arguments.get("query", ""))[:500], "mode": arguments.get("mode"), "limit": arguments.get("limit")}
        if logical == "ckk.read":
            return {"path": str(arguments.get("path", ""))[:500], "ref": arguments.get("ref")}
        if logical == "ckk.symbol":
            return {"name": str(arguments.get("name", ""))[:128], "limit": arguments.get("limit")}
        if logical == "ckk.run":
            return {
                "seed": str(arguments.get("seed", ""))[:128], "operators": list(arguments.get("operators") or []),
                "controls": list(arguments.get("controls") or []), "budgets": dict(arguments.get("budgets") or {}),
                "ref": arguments.get("ref"),
            }
        if logical == "research.publish":
            return {"run_id": str(arguments.get("run_id", ""))[:32]}
        if logical == "repo.read":
            return {
                "operation": arguments.get("operation"), "path": str(arguments.get("path") or "")[:500],
                "ref": arguments.get("ref"), "base_ref": arguments.get("base_ref"),
                "target_ref": arguments.get("target_ref"),
            }
        if logical == "process.run":
            return {
                "task": arguments.get("task"), "manifest_sha256": arguments.get("manifest_sha256"),
                "retry_of": arguments.get("retry_of"),
            }
        if logical in {"process.status", "process.stop", "system.metrics"}:
            return {"job_id": arguments.get("job_id")}
        if logical == "file.read":
            return {
                "path": str(arguments.get("path", ""))[:800], "offset": arguments.get("offset"),
                "maximum_chars": arguments.get("maximum_chars"),
            }
        if logical == "file.hash":
            return {"path": str(arguments.get("path", ""))[:800]}
        return {"text_length": len(str(arguments.get("text", "")))}

    @staticmethod
    def _bounded_for_model(logical: str, result: dict[str, Any]) -> dict[str, Any]:
        bounded = deepcopy(result)
        if logical in {"ckk.search", "ckk.symbol"}:
            remaining = 14000
            for item in bounded.get("items", []):
                excerpt = str(item.get("excerpt") or "")[: min(4000, remaining)]
                item["excerpt"] = excerpt
                remaining -= len(excerpt)
            bounded["items"] = bounded.get("items", [])[:10]
        elif logical == "ckk.read":
            bounded["excerpt"] = str(bounded.get("excerpt") or "")[:16000]
        elif logical == "ckk.run":
            provenance = bounded.get("provenance", [])
            bounded["provenance"] = provenance[:100]
            bounded["provenance_truncated_for_context"] = len(provenance) > 100
            bounded["complete_provenance_artifact"] = bounded.get("artifact")
        elif logical == "repo.read" and "excerpt" in bounded:
            bounded["excerpt"] = str(bounded.get("excerpt") or "")[:16000]
        elif logical == "file.read":
            bounded["excerpt"] = str(bounded.get("excerpt") or "")[:32000]
        elif logical == "process.status" and isinstance(bounded.get("jobs"), list):
            bounded["jobs"] = bounded["jobs"][:20]
        return bounded

    def status(self) -> dict[str, Any]:
        return {
            "capabilities": list(self.capabilities),
            "definition_sha256": self.definition_sha256,
            "namespaces": [item["name"] for item in self.definitions],
            "response_tool_definitions": {
                item["name"]: [tool["name"] for tool in item.get("tools", [])] for item in self.definitions
            },
            "invocation_count_since_start": len(self.invocations),
            "last_invocations": self.invocations[-12:],
        }
