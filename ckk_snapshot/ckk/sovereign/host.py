"""Deployable ASGI host for the sovereign organism."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import asyncio
import hashlib
import logging
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .brain import OpenAIResponsesCognition
from .knowledge import CKKKnowledgeClient
from .organism import SovereignOrganism
from .runtime import CapabilityPolicy, IngressPolicy, Observation, RuntimePhase, SovereignRuntime
from .state import SQLiteStateStore
from .telemetry import HttpTelemetrySink, NullTelemetrySink, TelemetrySink, sanitized_observation
from .whatsapp import (
    SERVICE_WINDOW_SECONDS,
    WhatsAppCloudActuator,
    WhatsAppConfig,
    WhatsAppInbox,
    extract_delivery_statuses,
    verify_challenge,
)


logger = logging.getLogger("uvicorn.error")


PRIVACY_POLICY_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KAIROS Privacy Policy</title></head>
<body style="max-width:760px;margin:3rem auto;padding:0 1rem;font:16px/1.55 system-ui,sans-serif">
<h1>KAIROS Privacy Policy</h1>
<p><strong>Last updated:</strong> 29 August 2026</p>
<p>KAIROS is a WhatsApp-based assistant operated by Worldom.</p>
<h2>Data processed</h2>
<p>When you contact KAIROS, the service processes your WhatsApp identifier, message content,
timestamps, media metadata, and message delivery status. Security and reliability logs contain
request metadata but are not used for advertising.</p>
<h2>Purpose and processors</h2>
<p>Data is processed to authenticate incoming messages, generate and deliver replies, prevent
abuse, and keep the service reliable. Meta/WhatsApp transports messages, OpenAI provides the
language-model service, and DigitalOcean hosts the application and its operational data.</p>
<h2>Retention and sharing</h2>
<p>Operational data is retained only as long as needed to provide and secure the service or meet
legal obligations. Worldom does not sell personal data. Data is shared only with the processors
named above as required to operate KAIROS.</p>
<h2 id="deletion">Access and deletion</h2>
<p>You may request access to or deletion of your KAIROS data by emailing
<a href="mailto:roberto.omezzolli@gmail.com">roberto.omezzolli@gmail.com</a>. Include the WhatsApp
number used to contact KAIROS so the records can be located.</p>
</body></html>"""


def _event_ref(event_id: str) -> str:
    return hashlib.sha256(event_id.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class HostSettings:
    owner_wa_id: str
    business_phone_number_id: str
    meta_app_secret: str
    meta_verify_token: str
    whatsapp_access_token: str
    allowed_wa_ids: tuple[str, ...] = ()
    openai_model: str = "gpt-5.6"
    state_path: str = "/data/sovereign.sqlite3"
    allowed_templates: tuple[str, ...] = ()
    template_language_code: str = "en_US"
    clock_interval_seconds: int = 900
    observatory_ingest_url: str = ""
    observatory_ingest_token: str = ""
    subject_version: str = "unknown"
    ckk_adapter_url: str = ""
    ckk_adapter_token: str = ""
    ckk_maximum_results: int = 6

    @classmethod
    def from_env(cls) -> "HostSettings":
        required = {
            "owner_wa_id": os.getenv("OWNER_WA_ID", ""),
            "business_phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            "meta_app_secret": os.getenv("META_APP_SECRET", ""),
            "meta_verify_token": os.getenv("META_VERIFY_TOKEN", ""),
            "whatsapp_access_token": os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError("missing required settings: " + ", ".join(missing))
        templates = tuple(item.strip() for item in os.getenv("WHATSAPP_ALLOWED_TEMPLATES", "").split(",") if item.strip())
        allowed_wa_ids = tuple(
            item.strip() for item in os.getenv("WHATSAPP_ALLOWED_WA_IDS", "").split(",") if item.strip()
        )
        return cls(
            **required,
            allowed_wa_ids=allowed_wa_ids,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            state_path=os.getenv("SOVEREIGN_STATE_PATH", "/data/sovereign.sqlite3"),
            allowed_templates=templates,
            template_language_code=os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en_US"),
            clock_interval_seconds=int(os.getenv("CLOCK_INTERVAL_SECONDS", "900")),
            observatory_ingest_url=os.getenv("OBSERVATORY_INGEST_URL", ""),
            observatory_ingest_token=os.getenv("OBSERVATORY_INGEST_TOKEN", ""),
            subject_version=os.getenv("SOVEREIGN_SUBJECT_VERSION", "unknown"),
            ckk_adapter_url=os.getenv("CKK_ADAPTER_URL", ""),
            ckk_adapter_token=os.getenv("CKK_ADAPTER_TOKEN", ""),
            ckk_maximum_results=max(1, min(10, int(os.getenv("CKK_MAXIMUM_RESULTS", "6")))),
        )


def build_organism(
    settings: HostSettings,
    store: SQLiteStateStore,
    client: Any = None,
    transport: Any = None,
):
    config = WhatsAppConfig(
        settings.owner_wa_id,
        settings.business_phone_number_id,
        frozenset(settings.allowed_templates),
        template_language_code=settings.template_language_code,
        additional_wa_ids=frozenset(settings.allowed_wa_ids),
    )
    inbox = WhatsAppInbox(config)
    actuator_args = {
        "config": config,
        "inbox": inbox,
        "access_token": settings.whatsapp_access_token,
    }
    if transport is not None:
        actuator_args["transport"] = transport
    actuator = WhatsAppCloudActuator(**actuator_args)
    runtime = SovereignRuntime(
        ingress=IngressPolicy(
            frozenset({"internal.clock", "ckk.repository", *(f"whatsapp:{item}" for item in config.admitted_wa_ids)}),
            frozenset({
                "clock.tick", "message.text", "message.document", "message.image", "message.audio",
                "evidence.source",
            }),
            maximum_payload_bytes=64 * 1024,
        ),
        capabilities=CapabilityPolicy(frozenset({"whatsapp.send"}), maximum_effects_per_wake=1),
        actuators={"whatsapp.send": actuator},
    )
    brain = OpenAIResponsesCognition(
        whatsapp=config,
        client=client,
        model=settings.openai_model,
        history_provider=store.recent_episodes,
        service_window_provider=lambda recipient: (
            recipient is not None
            and inbox.last_message_at(recipient) is not None
            and int(time.time()) - int(inbox.last_message_at(recipient) or 0) <= SERVICE_WINDOW_SECONDS
        ),
    )
    organism = SovereignOrganism(runtime, brain)
    store.restore(organism)
    windows, proactive = store.communication_state()
    inbox.last_message_at_by_sender.update(windows)
    inbox.last_owner_message_at = windows.get(config.owner_wa_id)
    actuator.proactive_timestamps = proactive
    return organism, inbox


def create_app(
    settings: HostSettings | None = None,
    client: Any = None,
    transport: Any = None,
    telemetry: TelemetrySink | None = None,
    knowledge: CKKKnowledgeClient | None = None,
):
    settings = settings or HostSettings.from_env()
    os.makedirs(os.path.dirname(os.path.abspath(settings.state_path)), exist_ok=True)
    store = SQLiteStateStore(settings.state_path)
    store.retry_stale()
    organism, inbox = build_organism(settings, store, client, transport)
    if telemetry is None and settings.observatory_ingest_url:
        telemetry = HttpTelemetrySink(
            settings.observatory_ingest_url,
            settings.observatory_ingest_token,
            settings.subject_version,
            settings.openai_model,
        )
    telemetry = telemetry or NullTelemetrySink()
    knowledge = knowledge or CKKKnowledgeClient(
        settings.ckk_adapter_url,
        settings.ckk_adapter_token,
        maximum_results=settings.ckk_maximum_results,
    )
    app = FastAPI(title="Sovereign Fixpoint Organism", docs_url=None, redoc_url=None)
    stop = asyncio.Event()

    def process(observation: Observation) -> None:
        event_ref = _event_ref(observation.observation_id)
        started = time.monotonic()
        pre_identity = organism.identity
        pre_memory_count = len(organism.runtime.memory)
        pre_belief_count = len(organism.learner.beliefs)
        ref_function = getattr(telemetry, "opaque_ref", lambda value: hashlib.sha256(value.encode()).hexdigest()[:24])
        session_id = ref_function(observation.sensor) if observation.sensor.startswith("whatsapp:") else None
        structural = sanitized_observation(observation, ref_function)
        telemetry.emit(
            "OBSERVED", structural, session_id=session_id,
            memory_version=organism.runtime.memory[-1].commit_id if organism.runtime.memory else "genesis",
            tool_state_version=hashlib.sha256("whatsapp.send".encode()).hexdigest(),
        )
        logger.info("observation processing started event_ref=%s kind=%s", event_ref, observation.kind)
        try:
            if observation.sensor.startswith("whatsapp:") and observation.payload.get("timestamp") is not None:
                timestamp = int(observation.payload["timestamp"])
                inbox.record_message(observation.sensor.removeprefix("whatsapp:"), timestamp)
            organism.perceive(observation)
            ckk_evidence = knowledge.observations_for(observation)
            for evidence in ckk_evidence:
                organism.perceive(evidence)
            if ckk_evidence:
                store.record_external_evidence(observation.observation_id, ckk_evidence)
            recent = store.recent_episodes(1000)
            if observation.sensor.startswith("whatsapp:"):
                recent = [item for item in recent if (item.get("observation") or {}).get("sensor") == observation.sensor]
            telemetry.emit(
                "RETRIEVED",
                {"event_ref": structural["event_ref"], "episodic_count": min(len(recent), 24),
                 "committed_belief_count": pre_belief_count, "content_exported": False,
                 "ckk_external_evidence_count": len(ckk_evidence),
                 "ckk_commit_sha": knowledge.last_commit_sha},
                session_id=session_id,
            )
            effect = organism.think()
            commit = organism.sleep()
            store.complete(
                observation,
                {
                    "observation": asdict(observation),
                    "effect": asdict(effect) if effect else None,
                    "commit": asdict(commit),
                    "beliefs": organism.learner.context(),
                },
                organism,
            )
            output = (effect.output if effect else {}) or {}
            provider = output.get("provider") if isinstance(output.get("provider"), dict) else {}
            if effect is not None:
                telemetry.emit(
                    "ACTED",
                    {"event_ref": structural["event_ref"], "capability": effect.capability,
                     "success": effect.success, "simulated": effect.simulated,
                     "provider_http_status": output.get("provider_http_status"),
                     "provider_message_count": len(provider.get("messages") or [])},
                    session_id=session_id, latency_ms=(time.monotonic() - started) * 1000,
                )
            else:
                telemetry.emit(
                    "ACTED", {"event_ref": structural["event_ref"], "capability": None,
                              "success": True, "action_class": "silence"},
                    session_id=session_id, latency_ms=(time.monotonic() - started) * 1000,
                )
            if len(organism.learner.beliefs) > pre_belief_count:
                telemetry.emit(
                    "LEARNED",
                    {"event_ref": structural["event_ref"], "belief_delta": len(organism.learner.beliefs) - pre_belief_count,
                     "belief_content_exported": False},
                    session_id=session_id,
                )
            telemetry.emit(
                "CONSOLIDATED",
                {"event_ref": structural["event_ref"],
                 "identity_chain_valid": commit.previous_identity == pre_identity and commit.identity == organism.identity,
                 "audit_chain_valid": organism.runtime.audit.valid(),
                 "memory_advanced": len(organism.runtime.memory) == pre_memory_count + 1,
                 "checkpoint_persisted": True, "sleep_cycle": "NREM_REM_WAKE"},
                session_id=session_id, memory_version=commit.runtime_commit,
            )
            logger.info(
                "observation processing completed event_ref=%s kind=%s effect=%s provider_http_status=%s provider_messages=%s",
                event_ref,
                observation.kind,
                effect is not None,
                output.get("provider_http_status"),
                len(provider.get("messages") or []),
            )
        except Exception as exc:
            wake_observation_ids = tuple(item.observation_id for item in organism.runtime.inbox)
            organism.runtime.pending_intent = None
            organism.runtime.inbox.clear()
            organism.runtime.effects.clear()
            organism._pending_learning.clear()
            for observation_id in wake_observation_ids:
                organism.runtime._seen_observations.discard(observation_id)
            organism.runtime._seen_observations.discard(observation.observation_id)
            organism.runtime.phase = RuntimePhase.WAKE
            store.fail(observation.observation_id, f"{type(exc).__name__}: {exc}")
            capability = None
            if organism.runtime.pending_intent is not None:
                capability = organism.runtime.pending_intent.capability
            telemetry.emit(
                "FAILED", {"event_ref": structural["event_ref"], "error_type": type(exc).__name__,
                           "capability": capability, "error_text_exported": False},
                session_id=session_id, latency_ms=(time.monotonic() - started) * 1000,
            )
            logger.exception(
                "observation processing failed event_ref=%s kind=%s error_type=%s error=%s",
                event_ref,
                observation.kind,
                type(exc).__name__,
                exc,
            )

    async def worker() -> None:
        while not stop.is_set():
            observation = store.next_observation()
            if observation is None:
                await asyncio.sleep(0.5)
                continue
            await asyncio.to_thread(process, observation)

    async def clock() -> None:
        while not stop.is_set():
            await asyncio.sleep(settings.clock_interval_seconds)
            now = int(time.time())
            store.enqueue((Observation(f"tick:{now}", "internal.clock", "clock.tick", {"unix_time": now}, 1.0),))

    @app.on_event("startup")
    async def start() -> None:
        app.state.worker = asyncio.create_task(worker())
        app.state.clock = asyncio.create_task(clock())
        telemetry.emit(
            "SELF_STATE_OBSERVED",
            {"phase": organism.runtime.phase.value,
             "memory_commits": len(organism.runtime.memory), "capabilities": sorted(organism.runtime.capabilities.allowed),
             "sensor_classes": sorted({
                 "whatsapp" if item.startswith("whatsapp:") else item for item in organism.runtime.ingress.sensors
             }), "checkpoint_restored": bool(organism.identity_history)},
            memory_version=organism.runtime.memory[-1].commit_id if organism.runtime.memory else "genesis",
            tool_state_version=hashlib.sha256("whatsapp.send".encode()).hexdigest(),
        )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        stop.set()
        for task in (app.state.worker, app.state.clock):
            task.cancel()
        telemetry.close()

    @app.get("/healthz")
    async def healthz():
        worker_task = getattr(app.state, "worker", None)
        clock_task = getattr(app.state, "clock", None)
        return {
            "status": "ok",
            "identity": organism.identity,
            "memory_commits": len(organism.runtime.memory),
            "queue": store.queue_stats(),
            "tasks": {
                "worker": "running" if worker_task is not None and not worker_task.done() else "stopped",
                "clock": "running" if clock_task is not None and not clock_task.done() else "stopped",
            },
            "ckk_knowledge": knowledge.health(),
        }

    @app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
    async def privacy_policy():
        return HTMLResponse(PRIVACY_POLICY_HTML)

    @app.get("/data-deletion", response_class=HTMLResponse, include_in_schema=False)
    async def data_deletion():
        return HTMLResponse(PRIVACY_POLICY_HTML)

    @app.get("/webhook")
    async def verify(request: Request):
        query = request.query_params
        try:
            challenge = verify_challenge(
                query.get("hub.mode", ""), query.get("hub.verify_token", ""),
                query.get("hub.challenge", ""), settings.meta_verify_token,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="verification rejected") from exc
        return PlainTextResponse(challenge)

    @app.post("/webhook", status_code=202)
    async def webhook(request: Request):
        raw = await request.body()
        signature = request.headers.get("x-hub-signature-256", "")
        try:
            observations = inbox.parse(raw, signature, settings.meta_app_secret)
            delivery_statuses = extract_delivery_statuses(raw)
            admitted = store.enqueue(observations)
        except (PermissionError, ValueError) as exc:
            logger.warning("WhatsApp webhook rejected reason=%s", exc)
            return JSONResponse({"status": "rejected", "reason": str(exc)}, status_code=403)
        logger.info(
            "WhatsApp webhook parsed observations=%s admitted=%s duplicates=%s delivery_statuses=%s",
            len(observations),
            admitted,
            len(observations) - admitted,
            len(delivery_statuses),
        )
        for delivery_status in delivery_statuses:
            logger.info(
                "WhatsApp delivery status message_ref=%s status=%s timestamp=%s",
                _event_ref(delivery_status.message_id),
                delivery_status.status,
                delivery_status.timestamp,
            )
            telemetry.emit(
                "OUTBOUND_DELIVERY",
                {"message_ref": _event_ref(delivery_status.message_id), "status": delivery_status.status,
                 "provider_timestamp": delivery_status.timestamp},
            )
        return {"status": "queued", "admitted": admitted, "duplicates": len(observations) - admitted}

    return app
