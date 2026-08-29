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
from fastapi.responses import JSONResponse, PlainTextResponse

from .brain import OpenAIResponsesCognition
from .deadman import DeadmanActuator, DeadmanGuard, DeadmanState
from .organism import SovereignOrganism
from .runtime import CapabilityPolicy, IngressPolicy, Observation, RuntimePhase, SovereignRuntime
from .state import SQLiteStateStore
from .whatsapp import (
    SERVICE_WINDOW_SECONDS,
    WhatsAppCloudActuator,
    WhatsAppConfig,
    WhatsAppInbox,
    extract_delivery_statuses,
    verify_challenge,
)


logger = logging.getLogger("uvicorn.error")


def _event_ref(event_id: str) -> str:
    return hashlib.sha256(event_id.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class HostSettings:
    owner_wa_id: str
    business_phone_number_id: str
    meta_app_secret: str
    meta_verify_token: str
    whatsapp_access_token: str
    openai_model: str = "gpt-5.6"
    state_path: str = "/data/sovereign.sqlite3"
    allowed_templates: tuple[str, ...] = ()
    template_language_code: str = "en_US"
    clock_interval_seconds: int = 900
    deadman_control_dir: str = "/control"

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
        return cls(
            **required,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            state_path=os.getenv("SOVEREIGN_STATE_PATH", "/data/sovereign.sqlite3"),
            allowed_templates=templates,
            template_language_code=os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en_US"),
            clock_interval_seconds=int(os.getenv("CLOCK_INTERVAL_SECONDS", "900")),
            deadman_control_dir=os.getenv("DEADMAN_CONTROL_DIR", "/control"),
        )


def build_organism(
    settings: HostSettings,
    store: SQLiteStateStore,
    client: Any = None,
    transport: Any = None,
    deadman: DeadmanGuard | None = None,
):
    config = WhatsAppConfig(
        settings.owner_wa_id,
        settings.business_phone_number_id,
        frozenset(settings.allowed_templates),
        template_language_code=settings.template_language_code,
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
    admitted_actuator = DeadmanActuator(actuator, deadman) if deadman is not None else actuator
    runtime = SovereignRuntime(
        ingress=IngressPolicy(
            frozenset({"internal.clock", f"whatsapp:{settings.owner_wa_id}"}),
            frozenset({"clock.tick", "message.text", "message.document", "message.image", "message.audio"}),
            maximum_payload_bytes=64 * 1024,
        ),
        capabilities=CapabilityPolicy(frozenset({"whatsapp.send"}), maximum_effects_per_wake=1),
        actuators={"whatsapp.send": admitted_actuator},
    )
    brain = OpenAIResponsesCognition(
        whatsapp=config,
        client=client,
        model=settings.openai_model,
        history_provider=store.recent_episodes,
        service_window_provider=lambda: (
            inbox.last_owner_message_at is not None
            and int(time.time()) - inbox.last_owner_message_at <= SERVICE_WINDOW_SECONDS
        ),
    )
    organism = SovereignOrganism(runtime, brain)
    store.restore(organism)
    last_owner, proactive = store.communication_state()
    inbox.last_owner_message_at = last_owner
    actuator.proactive_timestamps = proactive
    return organism, inbox


def create_app(settings: HostSettings | None = None, client: Any = None, transport: Any = None):
    settings = settings or HostSettings.from_env()
    os.makedirs(os.path.dirname(os.path.abspath(settings.state_path)), exist_ok=True)
    store = SQLiteStateStore(settings.state_path)
    store.retry_stale()
    deadman = DeadmanGuard.from_control_directory(settings.deadman_control_dir)
    organism, inbox = build_organism(settings, store, client, transport, deadman)
    app = FastAPI(title="Sovereign Fixpoint Organism", docs_url=None, redoc_url=None)
    stop = asyncio.Event()

    def process(observation: Observation) -> None:
        event_ref = _event_ref(observation.observation_id)
        logger.info("observation processing started event_ref=%s kind=%s", event_ref, observation.kind)
        try:
            if observation.sensor.startswith("whatsapp:") and observation.payload.get("timestamp") is not None:
                timestamp = int(observation.payload["timestamp"])
                inbox.last_owner_message_at = max(inbox.last_owner_message_at or 0, timestamp)
            organism.perceive(observation)
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
            logger.info(
                "observation processing completed event_ref=%s kind=%s effect=%s provider_http_status=%s provider_messages=%s",
                event_ref,
                observation.kind,
                effect is not None,
                output.get("provider_http_status"),
                len(provider.get("messages") or []),
            )
        except Exception as exc:
            organism.runtime.pending_intent = None
            organism.runtime.inbox.clear()
            organism.runtime.effects.clear()
            organism._pending_learning.clear()
            organism.runtime._seen_observations.discard(observation.observation_id)
            organism.runtime.phase = RuntimePhase.WAKE
            store.fail(observation.observation_id, f"{type(exc).__name__}: {exc}")
            logger.exception(
                "observation processing failed event_ref=%s kind=%s error_type=%s error=%s",
                event_ref,
                observation.kind,
                type(exc).__name__,
                exc,
            )

    async def worker() -> None:
        while not stop.is_set():
            if not deadman.evaluate().processing_allowed:
                await asyncio.sleep(1.0)
                continue
            observation = store.next_observation()
            if observation is None:
                await asyncio.sleep(0.5)
                continue
            await asyncio.to_thread(process, observation)

    async def clock() -> None:
        while not stop.is_set():
            await asyncio.sleep(settings.clock_interval_seconds)
            if not deadman.evaluate().processing_allowed:
                continue
            now = int(time.time())
            store.enqueue((Observation(f"tick:{now}", "internal.clock", "clock.tick", {"unix_time": now}, 1.0),))

    @app.on_event("startup")
    async def start() -> None:
        app.state.worker = asyncio.create_task(worker())
        app.state.clock = asyncio.create_task(clock())

    @app.on_event("shutdown")
    async def shutdown() -> None:
        stop.set()
        for task in (app.state.worker, app.state.clock):
            task.cancel()

    @app.get("/healthz")
    async def healthz():
        lease = deadman.evaluate()
        worker_task = getattr(app.state, "worker", None)
        clock_task = getattr(app.state, "clock", None)
        return {
            "status": "ok" if lease.state is DeadmanState.ACTIVE else lease.state.value,
            "deadman": {
                "state": lease.state.value,
            },
            "identity": organism.identity,
            "memory_commits": len(organism.runtime.memory),
            "queue": store.queue_stats(),
            "tasks": {
                "worker": "running" if worker_task is not None and not worker_task.done() else "stopped",
                "clock": "running" if clock_task is not None and not clock_task.done() else "stopped",
            },
        }

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
        lease = deadman.evaluate()
        if not lease.ingress_allowed:
            return JSONResponse({"status": "quarantined"}, status_code=423)
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
        return {"status": "queued", "admitted": admitted, "duplicates": len(observations) - admitted}

    return app
