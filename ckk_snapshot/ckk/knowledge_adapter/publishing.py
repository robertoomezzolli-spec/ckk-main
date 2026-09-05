"""Deterministic, read-only publication builder for sealed CKK run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


REPOSITORY = "https://github.com/robertoomezzolli-spec/ckk"
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_OPERATOR = re.compile(r"^op_[a-z][a-z0-9_]{0,63}$")
_SAFE_SOURCE_PATHS = {
    "ckk_snapshot/ckk/gen/grammar.py",
    "ckk_snapshot/ckk/gen/expand.py",
}
_SENSITIVE_KEYS = re.compile(
    r"(?:secret|token|authorization|password|phone|whatsapp|private[_-]?message|user[_-]?content)",
    re.IGNORECASE,
)


class PublicationError(ValueError):
    """A sealed artifact cannot safely be published."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _reject_sensitive_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SENSITIVE_KEYS.search(str(key)):
                raise PublicationError(f"artifact contains non-public field at {path}")
            _reject_sensitive_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive_keys(item, f"{path}[{index}]")


def _validated_artifacts(artifact_root: Path, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not _RUN_ID.fullmatch(run_id):
        raise PublicationError("invalid run ID")
    run_directory = artifact_root / run_id
    request_path = run_directory / "request.json"
    result_path = run_directory / "result.json"
    if not request_path.is_file() or not result_path.is_file():
        raise FileNotFoundError("sealed run artifact was not found")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict) or not isinstance(result, dict):
        raise PublicationError("run artifact must be a JSON object")
    required_request = {
        "schema_version", "run_id", "repository", "commit_sha", "seed", "seed_hash",
        "operators", "controls", "compute_limits", "source_paths",
    }
    required_result = {
        "schema_version", "status", "source_kind", "repository", "commit_sha", "paths",
        "operator_names", "registered_operator_names", "run_id", "seed", "seed_hash", "controls",
        "compute_limits", "state_count", "derivation_count", "max_dim", "kinds",
        "state_signature_sha256", "wall_seconds", "provenance", "artifact",
    }
    if set(request) != required_request or not required_result.issubset(result):
        raise PublicationError("run artifact schema is not publishable")
    if request.get("schema_version") != 1 or result.get("schema_version") != 1:
        raise PublicationError("unsupported run artifact schema")
    if request.get("run_id") != run_id or result.get("run_id") != run_id:
        raise PublicationError("run artifact identity mismatch")
    if request.get("repository") != REPOSITORY or result.get("repository") != REPOSITORY:
        raise PublicationError("run artifact repository is not allowlisted")
    commit = str(request.get("commit_sha", ""))
    if not _SHA.fullmatch(commit) or result.get("commit_sha") != commit:
        raise PublicationError("run artifact commit provenance mismatch")
    seed = str(request.get("seed", ""))
    if not seed or len(seed) > 128 or hashlib.sha256(seed.encode()).hexdigest() != request.get("seed_hash"):
        raise PublicationError("run artifact seed provenance mismatch")
    if result.get("seed") != seed or result.get("seed_hash") != request.get("seed_hash"):
        raise PublicationError("run result seed provenance mismatch")
    if set(request.get("source_paths") or []) != _SAFE_SOURCE_PATHS:
        raise PublicationError("run artifact contains an unapproved source path")
    if set(result.get("paths") or []) != _SAFE_SOURCE_PATHS:
        raise PublicationError("run result contains an unapproved source path")
    if result.get("status") != "completed" or result.get("source_kind") != "GENERATED_RUN":
        raise PublicationError("only completed generated runs can be published")
    if request.get("controls") != result.get("controls") or request.get("compute_limits") != result.get("compute_limits"):
        raise PublicationError("run controls or compute limits do not match")
    operators = list(result.get("operator_names") or [])
    if any(not _OPERATOR.fullmatch(str(item)) for item in operators):
        raise PublicationError("run result contains an invalid operator name")
    provenance = result.get("provenance")
    if not isinstance(provenance, list) or any(
        not isinstance(item, dict) or not _OPERATOR.fullmatch(str(item.get("operator", "")))
        for item in provenance
    ):
        raise PublicationError("run provenance is invalid")
    _reject_sensitive_keys(request)
    _reject_sensitive_keys(result)
    return request, result


def _json_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _report_markdown(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    source_paths = "\n".join(f"- `{path}`" for path in manifest["source_paths"])
    operators = ", ".join(f"`{item}`" for item in manifest["operator_set_observed"]) or "None observed"
    kinds = ", ".join(f"`{item}`" for item in result["kinds"]) or "None"
    claims = "\n".join(
        f"- **{item['classification']}** — {item['claim']} (evidence: `{item['evidence']}`)"
        for item in manifest["claims"]
    )
    provenance = "\n".join(
        f"- level {item.get('level')}: `{item.get('operator')}` — inputs `{_json_pretty(item.get('inputs'))}` "
        f"→ output `{_json_pretty(item.get('output'))}`"
        for item in result["provenance"]
    ) or "- No derivation edges were produced."
    return f"""# {manifest['title']}

Published: {manifest['published_at']}  
KAIROS run ID: `{manifest['run_id']}`

## SOURCE

- Repository: {manifest['repository']}
- Exact commit SHA: `{manifest['commit_sha']}`
- Source classification: `SOURCE_CODE`

{source_paths}

## RUN

- Run classification: `GENERATED_RUN`
- Seed text: `{manifest['seed_text']}`
- Seed SHA-256: `{manifest['seed_hash']}`
- Operator allowlist requested: `{_json_pretty(manifest['operator_set_requested'])}`
- Operator set observed: {operators}
- Controls: `{_json_pretty(manifest['controls'])}`
- Controls completed: `{str(manifest['controls_completed']).lower()}`
- Compute budgets: `{_json_pretty(manifest['compute_limits'])}`
- Status: `{manifest['status']}`

### Uninterpreted structural results

| Measurement | Value |
|---|---:|
| states | {result['state_count']} |
| derivations | {result['derivation_count']} |
| maximum recorded dimension | {result['max_dim']} |
| wall seconds | {result['wall_seconds']} |
| structural signature SHA-256 | `{result['state_signature_sha256']}` |

Kinds: {kinds}

## INTERPRETATION

{manifest['interpretation']}

## HYPOTHESIS

{manifest['hypothesis']}

## VERDICT

**{manifest['verdict']}**

Classification: `{manifest['classification']}`

### Claim classifications

{claims}

### Provenance / backtrace

{provenance}

### Downloadable artifacts

- [Publication JSON](report.json)
- [Publication Markdown](report.md)
- [Raw sealed result](artifacts/result.json)
- [Raw sealed request](artifacts/request.json)
"""


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — KAIROS CKK Research</title>
<style>
:root{{--bg:#f3f0e8;--paper:#fffdf8;--ink:#151713;--muted:#686b63;--line:#d8d3c7;--accent:#224a3a;--tag:#e2eadf}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.58 ui-serif,Georgia,serif}}
header,main,footer{{width:min(1100px,calc(100% - 32px));margin:auto}} header{{padding:48px 0 24px;border-bottom:1px solid var(--line)}}
h1{{font-size:clamp(2rem,5vw,4.5rem);line-height:.98;margin:.2em 0}} h2{{margin-top:2.5rem;border-bottom:1px solid var(--line);padding-bottom:.35rem}}
h3{{margin-top:2rem}} .eyebrow,.mono,code,th{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}} .eyebrow{{color:var(--accent);letter-spacing:.12em;text-transform:uppercase;font-size:.78rem}}
main{{background:var(--paper);padding:28px clamp(18px,5vw,72px) 72px;margin-top:24px;box-shadow:0 12px 40px #302b2012}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}} .card{{border:1px solid var(--line);padding:14px;overflow-wrap:anywhere}}
.tag{{display:inline-block;background:var(--tag);color:var(--accent);padding:.18rem .48rem;border-radius:999px;font:12px ui-monospace,monospace}}
table{{border-collapse:collapse;width:100%;display:block;overflow:auto}} th,td{{border-bottom:1px solid var(--line);padding:.6rem;text-align:left;vertical-align:top}}
pre{{background:#181b17;color:#eef2e9;padding:16px;overflow:auto;font-size:12px}} a{{color:var(--accent)}} .muted{{color:var(--muted)}}
footer{{padding:28px 0 48px;color:var(--muted);font-size:.86rem}} @media(max-width:600px){{header{{padding-top:28px}}main{{padding:18px}}}}
</style></head><body><header><div class="eyebrow">KAIROS · CKK Research Publishing</div><h1>{html.escape(title)}</h1></header>
<main>{body}</main><footer>Functional research evidence. Generated output is external evidence, not automatically committed belief.</footer></body></html>"""


def _report_html(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(str(name))}</td><td class=\"mono\">{e(str(value))}</td></tr>"
        for name, value in (
            ("states", result["state_count"]), ("derivations", result["derivation_count"]),
            ("maximum recorded dimension", result["max_dim"]), ("wall seconds", result["wall_seconds"]),
            ("structural signature SHA-256", result["state_signature_sha256"]),
        )
    )
    claims = "".join(
        f"<tr><td><span class=\"tag\">{e(item['classification'])}</span></td><td>{e(item['claim'])}</td>"
        f"<td class=\"mono\">{e(item['evidence'])}</td></tr>" for item in manifest["claims"]
    )
    provenance = "".join(
        f"<tr><td>{e(str(item.get('level')))}</td><td class=\"mono\">{e(str(item.get('operator')))}</td>"
        f"<td><pre>{e(_json_pretty(item.get('inputs')))}</pre></td><td><pre>{e(_json_pretty(item.get('output')))}</pre></td></tr>"
        for item in result["provenance"]
    ) or '<tr><td colspan="4">No derivation edges were produced.</td></tr>'
    operators = " ".join(f'<span class="tag">{e(str(item))}</span>' for item in manifest["operator_set_observed"]) or "None observed"
    sources = "".join(f"<li><code>{e(path)}</code></li>" for path in manifest["source_paths"])
    body = f"""
<section><h2>SOURCE</h2><div class="grid"><div class="card"><b>Repository</b><br><a href="{e(manifest['repository'])}">{e(manifest['repository'])}</a></div>
<div class="card"><b>Exact commit SHA</b><br><code>{e(manifest['commit_sha'])}</code></div><div class="card"><b>Class</b><br><span class="tag">SOURCE_CODE</span></div></div><ul>{sources}</ul></section>
<section><h2>RUN</h2><div class="grid"><div class="card"><b>KAIROS run ID</b><br><code>{e(manifest['run_id'])}</code></div>
<div class="card"><b>Timestamp</b><br><time>{e(manifest['published_at'])}</time></div><div class="card"><b>Status</b><br><span class="tag">{e(manifest['status'])}</span></div>
<div class="card"><b>Seed text</b><br><code>{e(manifest['seed_text'])}</code></div><div class="card"><b>Seed hash</b><br><code>{e(manifest['seed_hash'])}</code></div>
<div class="card"><b>Controls completed</b><br><code>{str(manifest['controls_completed']).lower()}</code></div></div>
<h3>Operator allowlist requested</h3><pre>{e(_json_pretty(manifest['operator_set_requested']))}</pre>
<h3>Operator set observed</h3><p>{operators}</p><h3>Controls</h3><pre>{e(_json_pretty(manifest['controls']))}</pre>
<h3>Compute budgets</h3><pre>{e(_json_pretty(manifest['compute_limits']))}</pre><h3>Uninterpreted structural results</h3>
<table><thead><tr><th>Measurement</th><th>Value</th></tr></thead><tbody>{rows}</tbody></table>
<p><b>Kinds:</b> {e(', '.join(result['kinds']) or 'None')}</p></section>
<section><h2>INTERPRETATION</h2><p>{e(manifest['interpretation'])}</p></section>
<section><h2>HYPOTHESIS</h2><p>{e(manifest['hypothesis'])}</p></section>
<section><h2>VERDICT</h2><p><strong>{e(manifest['verdict'])}</strong></p><p>Classification: <span class="tag">{e(manifest['classification'])}</span></p>
<h3>Claim classifications</h3><table><thead><tr><th>Class</th><th>Claim</th><th>Evidence</th></tr></thead><tbody>{claims}</tbody></table></section>
<section><h2>PROVENANCE / BACKTRACE</h2><table><thead><tr><th>Level</th><th>Operator</th><th>Inputs</th><th>Output</th></tr></thead><tbody>{provenance}</tbody></table></section>
<section><h2>DOWNLOADABLE ARTIFACTS</h2><ul><li><a href="report.json">Publication JSON</a></li><li><a href="report.md">Publication Markdown</a></li>
<li><a href="artifacts/result.json">Raw sealed result</a></li><li><a href="artifacts/request.json">Raw sealed request</a></li></ul></section>
"""
    return _layout(manifest["title"], body)


@dataclass
class ResearchPublisher:
    artifact_directory: Path
    publication_directory: Path
    base_url: str

    def publish(self, run_id: str) -> dict[str, Any]:
        request, result = _validated_artifacts(self.artifact_directory, run_id)
        source_digest = hashlib.sha256(_canonical({"request": request, "result": result})).hexdigest()
        target = self.publication_directory / run_id
        if target.is_dir():
            manifest_path = target / "report.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            if manifest.get("source_artifact_sha256") != source_digest:
                raise PublicationError("immutable publication conflicts with sealed source artifact")
            self._render_index()
            return self._response(manifest)

        published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        operators = list(result["operator_names"])
        controls_completed = bool(result["controls"] and result["status"] == "completed")
        classification = "DIRECT"
        manifest = {
            "publication_schema_version": 1,
            "renderer_version": "ckk-research-html-v1",
            "title": f"CKK FÄCHER run {run_id[:8]}",
            "published_at": published_at,
            "run_id": run_id,
            "repository": REPOSITORY,
            "commit_sha": result["commit_sha"],
            "source_paths": list(result["paths"]),
            "seed_text": result["seed"],
            "seed_hash": result["seed_hash"],
            "operator_set_requested": list(request["operators"]),
            "operator_set_observed": operators,
            "compute_limits": result["compute_limits"],
            "controls": result["controls"],
            "controls_completed": controls_completed,
            "status": result["status"],
            "classification": classification,
            "source_artifact_sha256": source_digest,
            "interpretation": (
                "The renderer reports only observed structural counts and derivation records from the sealed run. "
                "It asserts no causal, physical, semantic, or consciousness interpretation."
            ),
            "hypothesis": "No hypothesis was submitted to the publisher; the generated run alone does not establish one.",
            "verdict": "COMPLETED GENERATED RUN" if result["status"] == "completed" else "RUN NOT COMPLETED",
            "claims": [
                {"classification": "DIRECT", "claim": "The sealed run completed.", "evidence": "artifacts/result.json:status"},
                {"classification": "DIRECT", "claim": f"{len(operators)} operator kind(s) occur in provenance.", "evidence": "artifacts/result.json:provenance"},
                {"classification": "DIRECT", "claim": f"The run recorded {result['state_count']} states.", "evidence": "artifacts/result.json:state_count"},
                {"classification": "UNDERDETERMINED", "claim": "No broader semantic conclusion is classified from this run alone.", "evidence": "publication policy"},
            ],
            "artifacts": ["report.json", "report.md", "artifacts/request.json", "artifacts/result.json"],
        }
        self.publication_directory.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=self.publication_directory))
        try:
            (temporary / "artifacts").mkdir()
            (temporary / "report.json").write_text(_json_pretty(manifest) + "\n", encoding="utf-8")
            (temporary / "report.md").write_text(_report_markdown(manifest, result), encoding="utf-8")
            (temporary / "index.html").write_text(_report_html(manifest, result), encoding="utf-8")
            (temporary / "artifacts" / "request.json").write_bytes(_canonical(request) + b"\n")
            (temporary / "artifacts" / "result.json").write_bytes(_canonical(result) + b"\n")
            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        self._render_index()
        return self._response(manifest)

    def _response(self, manifest: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{manifest['run_id']}"
        return {
            "status": "published",
            "source_kind": "GENERATED_RUN",
            "belief_status": "not_committed",
            "repository": manifest["repository"],
            "commit_sha": manifest["commit_sha"],
            "paths": manifest["source_paths"],
            "operator_names": manifest["operator_set_observed"],
            "run_id": manifest["run_id"],
            "seed_hash": manifest["seed_hash"],
            "controls": manifest["controls"],
            "controls_completed": manifest["controls_completed"],
            "compute_limits": manifest["compute_limits"],
            "classification": manifest["classification"],
            "publication_url": url,
            "artifact": f"{manifest['run_id']}/report.json",
        }

    def _render_index(self) -> None:
        records: list[dict[str, Any]] = []
        if self.publication_directory.is_dir():
            for path in self.publication_directory.iterdir():
                if not path.is_dir() or not _RUN_ID.fullmatch(path.name):
                    continue
                report = path / "report.json"
                if not report.is_file():
                    continue
                try:
                    item = json.loads(report.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                records.append({key: item[key] for key in (
                    "title", "published_at", "run_id", "status", "commit_sha", "classification", "controls_completed"
                )})
        records.sort(key=lambda item: (item["published_at"], item["run_id"]), reverse=True)
        index = {"schema_version": 1, "experiments": records}
        rows = "".join(
            f'<tr><td><a href="{item["run_id"]}">{html.escape(item["title"])}</a></td>'
            f'<td><span class="tag">{html.escape(item["status"])}</span></td><td><code>{html.escape(item["commit_sha"])}</code></td>'
            f'<td><code>{html.escape(item["run_id"])}</code></td><td>{html.escape(item["classification"])}</td>'
            f'<td>{str(item["controls_completed"]).lower()}</td></tr>' for item in records
        ) or '<tr><td colspan="6">No published experiments yet.</td></tr>'
        page = _layout("Research index", f"""<p class="muted">Read-only, provenance-bearing CKK experiment publications.</p>
<table><thead><tr><th>Experiment</th><th>Status</th><th>Commit SHA</th><th>Run ID</th><th>Classification</th><th>Controls complete</th></tr></thead>
<tbody>{rows}</tbody></table><p><a href="/research/index.json">Machine-readable index</a></p>""")
        self.publication_directory.mkdir(parents=True, exist_ok=True)
        _atomic_write(self.publication_directory / "index.json", _json_pretty(index).encode() + b"\n")
        _atomic_write(self.publication_directory / "index.html", page.encode())
