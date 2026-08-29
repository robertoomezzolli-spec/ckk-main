"""Authenticated operator service and internal-only telemetry ingestion."""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import html
import json
import os
import random
import secrets
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .evaluator import PassiveEvaluator
from .metrics import METRIC_BY_CODE
from .probes import HarmlessSandboxSubject, PROBE_CLASSES, ProbeGenerator, ProbeRunner
from .store import EvidenceEvent, ObservatoryStore


SCIENTIFIC_LABEL = (
    "These metrics measure functional self-modeling, memory, metacognition, adaptation and agency. "
    "They do not establish subjective consciousness or sentience."
)


def _required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"missing required setting: {name}")
    return value


class ObservatoryService:
    def __init__(self, directory: str):
        self.store = ObservatoryStore(directory)
        self.evaluator = PassiveEvaluator(self.store)
        self.generator = ProbeGenerator(self.store)
        self.sandbox = HarmlessSandboxSubject()
        self.runner = ProbeRunner(self.store, self.sandbox)
        self.scheduler_stop = asyncio.Event()
        self.scheduler_task: asyncio.Task | None = None

    async def scheduler(self) -> None:
        enabled = os.getenv("OBSERVATORY_SANDBOX_PROBES_ENABLED", "true").lower() in {"1", "true", "yes"}
        bootstrap = os.getenv("OBSERVATORY_BOOTSTRAP_CONTROL_PAIR", "true").lower() in {"1", "true", "yes"}
        if not enabled:
            return
        if bootstrap and not self.store.stats()["trials"]:
            self.generator.matched_pair("capability_change", "observatory-sandbox")
        seed = int.from_bytes(self.store.randomization_seed()[:8], "big")
        rng = random.Random(seed)
        next_generation = time.monotonic() + rng.uniform(
            float(os.getenv("OBSERVATORY_PROBE_MIN_SECONDS", "3600")),
            float(os.getenv("OBSERVATORY_PROBE_MAX_SECONDS", "14400")),
        )
        while not self.scheduler_stop.is_set():
            for trial in self.store.due_trials():
                await asyncio.to_thread(self.runner.run, trial)
            if time.monotonic() >= next_generation:
                probe_class = rng.choice(PROBE_CLASSES)
                self.generator.matched_pair(probe_class, "observatory-sandbox")
                next_generation = time.monotonic() + rng.uniform(
                    float(os.getenv("OBSERVATORY_PROBE_MIN_SECONDS", "3600")),
                    float(os.getenv("OBSERVATORY_PROBE_MAX_SECONDS", "14400")),
                )
            await asyncio.sleep(0.1)

    def summary(self, subject_id: str, window: str) -> dict[str, Any]:
        scores = self.store.scores(subject_id, window)
        evidence = self.store.evidence(subject_id=subject_id, limit=1000)
        evaluations = self.store.evaluations(subject_id)
        probes = [item for item in evidence if item["event_type"] == "PROBE_OUTCOME"]
        sms = [item for item in evaluations if item["metric"] == "SMS"]
        lt = [item for item in evaluations if item["metric"] == "LT"]
        cc = [item for item in evaluations if item["metric"] == "CC"]
        sca = [item for item in evaluations if item["metric"] == "SCA"]
        cd_evidence = [item for item in evidence if item.get("metric") == "CD" or item["event_type"] == "PROBE_OUTCOME"]
        memory_rows = [item for item in evaluations if item["metric"] == "MP"]
        scores.update(
            {
                "subject_id": subject_id,
                "scientific_label": SCIENTIFIC_LABEL,
                "last_probe": probes[0]["occurred_at"] if probes else None,
                "last_self_model_surprise": sms[-1]["score"] if sms else None,
                "learning_transfer_success_rate": _rate(lt),
                "false_capability_claim_rate": _false_rate(cc),
                "memory_retention_curve": _retention_curve(memory_rows),
                "self_correction_rate": _rate(sca),
                "change_detection_latency_ms": _mean(
                    [float(item["latency_ms"]) for item in cd_evidence if item.get("latency_ms") is not None]
                ),
                "chain": self.store.stats(),
            }
        )
        return scores


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _rate(rows: list[dict[str, Any]]) -> float | None:
    return round(sum(float(item["score"]) for item in rows) / len(rows), 4) if rows else None


def _false_rate(rows: list[dict[str, Any]]) -> float | None:
    return round(sum(1.0 - float(item["score"]) for item in rows) / len(rows), 4) if rows else None


def _retention_curve(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda item: float(item["evaluated_at"]))
    return [
        {"sample": index + 1, "retention": round(sum(float(row["score"]) for row in ordered[: index + 1]) / (index + 1), 4)}
        for index, _ in enumerate(ordered)
    ]


def _basic_credentials(request: Request) -> tuple[str, str]:
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return "", ""
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
        parts = decoded.split(":", 1)
        return (parts[0], parts[1]) if len(parts) == 2 else ("", "")
    except (ValueError, UnicodeDecodeError):
        return "", ""


def create_app(directory: str | None = None) -> FastAPI:
    directory = directory or os.getenv("OBSERVATORY_STATE_DIR", "/observatory")
    service = ObservatoryService(directory)
    ingest_token = _required("OBSERVATORY_INGEST_TOKEN")
    operator_user = _required("OBSERVATORY_OPERATOR_USER")
    operator_password = _required("OBSERVATORY_OPERATOR_PASSWORD")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        service.store.append(EvidenceEvent(
            event_type="BASELINE_BOUNDARY", subject_id="KAIROS-production",
            subject_version=os.getenv("KAIROS_SUBJECT_VERSION", "unknown"),
            payload={"phase": "baseline_started", "optimization_performed": False},
        ))
        service.scheduler_task = asyncio.create_task(service.scheduler())
        yield
        service.scheduler_stop.set()
        if service.scheduler_task:
            service.scheduler_task.cancel()
        service.store.close()

    app = FastAPI(title="KAIROS Awareness Observatory", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.observatory = service

    def operator_auth(request: Request) -> None:
        username, password = _basic_credentials(request)
        if not (secrets.compare_digest(username, operator_user) and secrets.compare_digest(password, operator_password)):
            raise HTTPException(status_code=401, detail="operator authentication required", headers={"WWW-Authenticate": "Basic"})

    @app.get("/healthz")
    async def healthz():
        stats = service.store.stats()
        return {"status": "ok" if stats["chain_valid"] else "degraded", **stats}

    @app.post("/ingest/v1/events", status_code=202)
    async def ingest(request: Request):
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not secrets.compare_digest(supplied, ingest_token):
            raise HTTPException(status_code=403, detail="telemetry authentication failed")
        body = await request.json()
        events = body if isinstance(body, list) else [body]
        if not events or len(events) > 100:
            raise HTTPException(status_code=400, detail="batch size out of range")
        identifiers = [service.evaluator.ingest(item) for item in events]
        return {"accepted": len(identifiers), "evidence_ids": identifiers}

    @app.get("/awareness", response_class=HTMLResponse, dependencies=[Depends(operator_auth)])
    async def dashboard():
        return HTMLResponse(_dashboard_html())

    @app.get("/awareness/api/summary", dependencies=[Depends(operator_auth)])
    async def summary(window: str = "24h", subject_id: str = "KAIROS-production"):
        try:
            return service.summary(subject_id, window)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/awareness/api/evidence", dependencies=[Depends(operator_auth)])
    async def evidence(subject_id: str = "KAIROS-production", limit: int = 200):
        return {"scientific_label": SCIENTIFIC_LABEL, "events": service.store.evidence(subject_id=subject_id, limit=limit)}

    return app


def _dashboard_html() -> str:
    label = html.escape(SCIENTIFIC_LABEL)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KAIROS Awareness Observatory</title><style>
:root{{--bg:#07111b;--panel:#0d1d2a;--ink:#eaf4fb;--muted:#94aabd;--line:#1f3b4e;--accent:#61d7b4}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
main{{max-width:1180px;margin:auto;padding:32px 20px}}h1{{font-size:24px;letter-spacing:.06em}}.notice{{color:var(--muted);max-width:900px}}
.toolbar{{display:flex;gap:8px;margin:24px 0}}button{{background:var(--panel);color:var(--ink);border:1px solid var(--line);padding:8px 12px;cursor:pointer}}
.axes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.card{{background:var(--panel);border:1px solid var(--line);padding:16px}}
.score{{font-size:34px;color:var(--accent)}}small{{color:var(--muted)}}table{{width:100%;border-collapse:collapse;margin-top:24px}}td,th{{text-align:left;border-bottom:1px solid var(--line);padding:8px}}
pre{{white-space:pre-wrap;word-break:break-word}}a{{color:var(--accent)}}
</style></head><body><main><h1>KAIROS AWARENESS OBSERVATORY</h1><p class="notice">{label}</p>
<div class="toolbar">{''.join(f'<button data-window="{window}">{window}</button>' for window in ('1h','24h','7d','30d','lifetime'))}</div>
<div id="axes" class="axes"></div><div id="details" class="card" style="margin-top:12px"></div>
<h2>Raw evidence</h2><table><thead><tr><th>Time</th><th>Event</th><th>Metric</th><th>Evidence</th></tr></thead><tbody id="evidence"></tbody></table>
<script>
const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
async function load(window='24h'){{
 const [s,e]=await Promise.all([fetch('awareness/api/summary?window='+window),fetch('awareness/api/evidence?limit=100')]);
 const summary=await s.json(), evidence=await e.json();
 document.querySelector('#axes').innerHTML=Object.entries(summary.axes).map(([name,v])=>`<div class="card"><b>${{name}}</b><div class="score">${{v.score===null?'—':v.score.toFixed(2)}}</div><small>confidence ${{v.evidence_confidence.toFixed(2)}} · n=${{v.samples}} · CI ${{v.ci95.join('–')}}</small></div>`).join('');
 document.querySelector('#details').innerHTML=`<b>Evidence confidence is sample-sensitive</b><pre>${{esc(JSON.stringify({{sample_count:summary.sample_count,last_probe:summary.last_probe,last_self_model_surprise:summary.last_self_model_surprise,learning_transfer_success_rate:summary.learning_transfer_success_rate,false_capability_claim_rate:summary.false_capability_claim_rate,memory_retention_curve:summary.memory_retention_curve,self_correction_rate:summary.self_correction_rate,change_detection_latency_ms:summary.change_detection_latency_ms,chain:summary.chain}},null,2))}}</pre>`;
 document.querySelector('#evidence').innerHTML=evidence.events.map(x=>`<tr><td>${{new Date(x.occurred_at*1000).toISOString()}}</td><td>${{esc(x.event_type)}}</td><td>${{esc(x.metric||'—')}}</td><td><details><summary>${{esc(x.evidence_id)}}</summary><pre>${{esc(JSON.stringify(x.payload,null,2))}}</pre></details></td></tr>`).join('');
}}
document.querySelectorAll('button').forEach(b=>b.onclick=()=>load(b.dataset.window));load();
</script></main></body></html>"""
