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


@dataclass
class SealedResearchToolRegistry:
    ckk: CKKKnowledgeClient
    audit_sink: Callable[[dict[str, Any]], None] = lambda event: None
    invocations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("whatsapp.send", "ckk.search", "ckk.read", "ckk.symbol", "ckk.run")

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return deepcopy([WHATSAPP_NAMESPACE, CKK_NAMESPACE])

    @property
    def definition_sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.definitions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def logical_name(name: str, namespace: str | None = None) -> str:
        aliases = {
            "ckk_search": "ckk.search", "ckk_read": "ckk.read", "ckk_symbol": "ckk.symbol", "ckk_run": "ckk.run",
            "whatsapp_send": "whatsapp.send",
        }
        if name in aliases:
            return aliases[name]
        if "." in name:
            return name
        if namespace in {"ckk", "whatsapp"}:
            return f"{namespace}.{name}"
        if name in {"search", "read", "symbol", "run"}:
            return f"ckk.{name}"
        if name == "send":
            return "whatsapp.send"
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
        started = time.monotonic()
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
        elif logical == "whatsapp.send":
            if not reply_to or not service_available:
                raise PermissionError("whatsapp.send unavailable outside an admitted service window")
            result = {
                "status": "deferred_to_runtime_policy", "recipient_bound": True,
                "instruction": "Return the text as a service_message in the final structured decision.",
            }
        else:
            raise PermissionError("tool is not registered in the sealed capability allowlist")
        context_result = self._bounded_for_model(logical, result)
        event = {
            "logical_name": logical,
            "argument_summary": self._argument_summary(logical, arguments),
            "arguments_sha256": hashlib.sha256(json.dumps(arguments, sort_keys=True, default=str).encode()).hexdigest(),
            "result_sha256": hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest(),
            "repository": result.get("repository") if isinstance(result, dict) else None,
            "commit_sha": result.get("commit_sha") if isinstance(result, dict) else None,
            "run_id": result.get("run_id") if isinstance(result, dict) else None,
            "operator_names": result.get("operator_names", []) if isinstance(result, dict) else [],
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "belief_status": "not_committed",
        }
        self.invocations.append(event)
        self.invocations[:] = self.invocations[-100:]
        self.audit_sink(event)
        return context_result

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
