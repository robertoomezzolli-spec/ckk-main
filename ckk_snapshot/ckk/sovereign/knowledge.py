"""Bounded client for external CKK evidence.

This is a sensor adapter, not an actuator and not a memory loader.  It turns a
small number of read-only repository results into observations for one WAKE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any
import urllib.error
import urllib.request

from .runtime import Observation


_CKK_INTENT = re.compile(
    r"(?:\bckk\b|\bop_[a-z0-9_]+\b|\bmaxdim\b|run[- ]?34|f[aä]cher|grammar|"
    r"structural_sig|snapshot|audit|commit(?:s)?\b|source\s+(?:path|code)|"
    r"backtrace|provenance|evidence|dimension(?:al)?\s+(?:limit|cutoff|bound))",
    re.IGNORECASE,
)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,127}")


@dataclass
class CKKKnowledgeClient:
    base_url: str
    access_token: str
    maximum_results: int = 6
    maximum_total_chars: int = 12000
    timeout_seconds: float = 8.0
    last_commit_sha: str | None = None
    last_error_type: str | None = None
    retrievals: int = 0
    _opener: Any = field(default=urllib.request.urlopen, repr=False)

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.access_token)

    @staticmethod
    def relevant(query: str) -> bool:
        return bool(_CKK_INTENT.search(query))

    def observations_for(self, source: Observation) -> tuple[Observation, ...]:
        if not self.enabled or source.kind != "message.text":
            return ()
        query = str(source.payload.get("text", "")).strip()
        if not query or not self.relevant(query):
            return ()
        try:
            response = self._request("/v1/retrieve", {"query": query, "limit": self.maximum_results, "mode": "hybrid"})
            self.last_commit_sha = str(response.get("commit_sha") or "") or None
            self.last_error_type = None
            self.retrievals += 1
            return self._observations(source.observation_id, response, query)
        except Exception as exc:
            self.last_error_type = type(exc).__name__
            return ()

    def _request(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(),
            headers={"authorization": f"Bearer {self.access_token}", "content-type": "application/json"},
            method="POST",
        )
        with self._opener(request, timeout=self.timeout_seconds) as response:
            if int(response.status) != 200:
                raise RuntimeError(f"CKK adapter returned HTTP {response.status}")
            payload = json.loads(response.read(256 * 1024))
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("CKK adapter returned an invalid response")
        return payload

    def _observations(self, parent_id: str, response: dict[str, Any], query: str = "") -> tuple[Observation, ...]:
        history = [item for item in response.get("history", []) if isinstance(item, dict)]
        oldest = [item for item in history if item.get("history_position") == "oldest_matching_change"]
        recent = [item for item in history if item.get("history_position") != "oldest_matching_change"]
        diff_items = [item for item in response.get("diff", []) if isinstance(item, dict)]
        meaningful_terms = {
            term.lower() for term in _IDENTIFIER.findall(query)
            if len(term) >= 4 and term.lower() not in {"what", "changed", "between", "commit", "commits", "compare"}
        }
        if meaningful_terms:
            diff_items.sort(
                key=lambda item: -sum(
                    term in f"{item.get('path', '')}\n{item.get('excerpt', '')}".lower()
                    for term in meaningful_terms
                )
            )
        candidates: list[tuple[str, dict[str, Any]]] = []
        candidates.extend(("commit_diff", item) for item in diff_items[:2])
        candidates.extend(("commit_history", item) for item in [*oldest[:1], *recent[:1]])
        candidates.extend(("retrieved_chunk", item) for item in response.get("items", []))
        observations: list[Observation] = []
        remaining = self.maximum_total_chars
        for evidence_type, raw in candidates:
            if len(observations) >= self.maximum_results or remaining <= 0 or not isinstance(raw, dict):
                break
            required = ("repository", "commit_sha", "path", "source_kind", "evidence_labels")
            if any(not raw.get(field) for field in required):
                continue
            excerpt = str(raw.get("excerpt") or "")[: min(2800, remaining)]
            remaining -= len(excerpt)
            provenance = {
                "repository": str(raw["repository"]),
                "ref": str(raw.get("ref") or response.get("ref") or ""),
                "commit_sha": str(raw["commit_sha"]),
                "base_commit_sha": str(raw.get("base_commit_sha") or ""),
                "blob_sha": str(raw.get("blob_sha") or ""),
                "path": str(raw["path"]),
                "start_line": raw.get("start_line"),
                "end_line": raw.get("end_line"),
                "symbols": list(raw.get("symbols") or []),
                "source_kind": str(raw["source_kind"]),
                "evidence_labels": list(raw["evidence_labels"]),
                "content_sha256": str(raw.get("content_sha256") or ""),
                "retrieval_methods": list(raw.get("retrieval_methods") or []),
                "authored_at": str(raw.get("authored_at") or ""),
                "commit_subject": str(raw.get("subject") or ""),
                "history_position": str(raw.get("history_position") or ""),
                "history_term": str(raw.get("term") or ""),
                "truth_status": "external_evidence_unverified",
                "belief_status": "not_committed",
                "evidence_type": evidence_type,
            }
            fingerprint = json.dumps(provenance, sort_keys=True, separators=(",", ":"))
            observation_id = "ckk:" + hashlib.sha256(f"{parent_id}:{fingerprint}".encode()).hexdigest()
            observations.append(
                Observation(
                    observation_id=observation_id,
                    sensor="ckk.repository",
                    kind="evidence.source",
                    payload={**provenance, "excerpt": excerpt},
                    trust=0.75,
                )
            )
        return tuple(observations)

    def health(self) -> dict[str, Any]:
        return {
            "configured": self.enabled,
            "last_commit_sha": self.last_commit_sha,
            "last_error_type": self.last_error_type,
            "retrievals": self.retrievals,
        }
