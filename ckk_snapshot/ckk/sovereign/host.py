"""Deployable ASGI host for the sovereign organism."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import asyncio
import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .brain import OpenAIResponsesCognition
from .knowledge import CKKKnowledgeClient
from .organism import SovereignOrganism
from .runtime import CapabilityPolicy, IngressPolicy, Observation, RuntimePhase, SovereignRuntime
from .research_tools import SealedResearchToolRegistry
from .state import SQLiteStateStore
from .telemetry import HttpTelemetrySink, NullTelemetrySink, TelemetrySink, sanitized_observation
from .whatsapp import (
    SERVICE_WINDOW_SECONDS,
    WhatsAppCloudActuator,
    WhatsAppConfig,
    WhatsAppInbox,
    WhatsAppTransportError,
    extract_delivery_statuses,
    service_intent,
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


EXPERIMENT_TERMINAL_STATES = frozenset({
    "COMPLETED", "FAILED", "FAILED_EQUIVALENCE", "STOPPED", "TIMED_OUT",
    "MEMORY_LIMIT", "OOM_KILLED", "INTERRUPTED",
})


def experiment_completion_observation(job: dict[str, Any], recipient: str) -> Observation:
    """Create an ordinary operational status event; no Observatory data or artifact content is included."""

    job_id = str(job.get("job_id") or "")
    state = str(job.get("state") or "")
    if state not in EXPERIMENT_TERMINAL_STATES or len(job_id) != 32:
        raise ValueError("experiment completion requires a terminal sealed job")
    return Observation(
        observation_id=(
            f"experiment-job:{job_id}:{state}:"
            f"{job.get('result_sha256') or job.get('exit_code')}"
        ),
        sensor=f"whatsapp:{recipient}",
        kind="message.experiment_status",
        payload={
            "source": "sealed_experiment_supervisor",
            "job_id": job_id,
            "task": job.get("task"),
            "state": state,
            "commit_sha": job.get("commit_sha"),
            "manifest_sha256": job.get("manifest_sha256"),
            "exit_code": job.get("exit_code"),
            "termination_class": job.get("termination_class"),
            "runtime_seconds": job.get("runtime_seconds"),
            "peak_rss_bytes": job.get("peak_rss_bytes"),
            "result_path": job.get("result_path"),
            "result_sha256": job.get("result_sha256"),
            "equivalence_passed": job.get("equivalence_passed"),
            "content_exported": False,
        },
        trust=1.0,
    )


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
    knowledge: CKKKnowledgeClient | None = None,
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
                "message.experiment_status", "evidence.source",
            }),
            maximum_payload_bytes=64 * 1024,
        ),
        capabilities=CapabilityPolicy(frozenset({"whatsapp.send"}), maximum_effects_per_wake=1),
        actuators={"whatsapp.send": actuator},
    )
    knowledge = knowledge or CKKKnowledgeClient(settings.ckk_adapter_url, settings.ckk_adapter_token)
    tool_registry = SealedResearchToolRegistry(knowledge, audit_sink=store.record_tool_invocation)
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
        tool_registry=tool_registry,
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
    knowledge = knowledge or CKKKnowledgeClient(
        settings.ckk_adapter_url,
        settings.ckk_adapter_token,
        maximum_results=settings.ckk_maximum_results,
    )
    organism, inbox = build_organism(settings, store, client, transport, knowledge)
    if telemetry is None and settings.observatory_ingest_url:
        telemetry = HttpTelemetrySink(
            settings.observatory_ingest_url,
            settings.observatory_ingest_token,
            settings.subject_version,
            settings.openai_model,
        )
    telemetry = telemetry or NullTelemetrySink()
    audited_capabilities = {
        "repo.read",
        "process.run",
        "process.status",
        "process.stop",
        "file.read",
        "file.hash",
        "system.metrics",
        "whatsapp.send_to_allowed_person",
    }

    def record_tool_event(event: dict[str, Any]) -> None:
        store.record_tool_invocation(event)
        if event.get("logical_name") not in audited_capabilities:
            return
        if event.get("logical_name") == "whatsapp.send_to_allowed_person":
            telemetry.emit(
                "WHATSAPP_RELAY",
                {
                    "capability": event.get("logical_name"),
                    "requesting_participant": event.get("requesting_participant"),
                    "intended_recipient": event.get("intended_recipient"),
                    "start_time": event.get("started_at"),
                    "finish_time": event.get("finished_at"),
                    "status": event.get("status"),
                    "provider_http_status": event.get("provider_http_status"),
                    "provider_message_ref": (
                        _event_ref(str(event["provider_message_id"]))
                        if event.get("provider_message_id") else None
                    ),
                    "message_length": (event.get("argument_summary") or {}).get("message_length"),
                    "content_exported": False,
                    "phone_identifiers_exported": False,
                },
                latency_ms=event.get("latency_ms"),
            )
            return
        summary = event.get("argument_summary") if isinstance(event.get("argument_summary"), dict) else {}
        telemetry.emit(
            "CAPABILITY_INVOKED",
            {
                "capability": event.get("logical_name"),
                "operation": summary.get("operation") or summary.get("task"),
                "job_id": event.get("job_id") or summary.get("job_id"),
                "start_time": event.get("started_at"),
                "finish_time": event.get("finished_at"),
                "status": event.get("status"),
                "exit_status": event.get("exit_status"),
                "artifact_path": event.get("artifact_path"),
                "artifact_sha256": event.get("artifact_sha256"),
                "arguments_sha256": event.get("arguments_sha256"),
                "result_sha256": event.get("result_sha256"),
                "content_exported": False,
            },
            latency_ms=event.get("latency_ms"),
        )

    organism.cognition.tool_registry.audit_sink = record_tool_event

    def bind_experiment_job(job_id: str, recipient: str) -> None:
        if recipient not in inbox.config.admitted_wa_ids:
            raise PermissionError("experiment notification recipient is not admitted")
        store.bind_experiment_job(job_id, recipient)

    organism.cognition.tool_registry.job_binding_sink = bind_experiment_job

    def send_allowed_relay(
        request_event_id: str,
        requester_wa_id: str,
        intended_person: str,
        message: str,
    ) -> dict[str, Any]:
        contacts = inbox.config.relay_contacts
        requesting_person = inbox.config.relay_person_for_id(requester_wa_id)
        if requesting_person is None:
            raise PermissionError("relay requester is not in the sealed contact allowlist")
        if intended_person not in contacts:
            raise PermissionError("relay recipient is not in the sealed contact allowlist")
        if intended_person == requesting_person:
            raise PermissionError("relay must target the other allowed participant")
        reservation = store.reserve_whatsapp_relay(
            request_event_id, requesting_person, intended_person
        )
        if not reservation.get("new"):
            state = str(reservation.get("state"))
            if state == "ACCEPTED":
                return {
                    "status": "already_accepted",
                    "requesting_participant": requesting_person,
                    "intended_recipient": intended_person,
                    "provider_http_status": reservation.get("provider_http_status"),
                    "provider_message_id": reservation.get("meta_message_id"),
                    "delivery_status": reservation.get("delivery_status"),
                    "idempotent": True,
                    "belief_status": "not_committed",
                }
            error = (
                str(reservation.get("failure_type") or "provider rejected the relay")
                if state == "REJECTED"
                else "prior relay outcome is uncertain; duplicate send suppressed"
            )
            return {
                "status": "rejected" if state == "REJECTED" else "uncertain",
                "requesting_participant": requesting_person,
                "intended_recipient": intended_person,
                "provider_http_status": reservation.get("provider_http_status"),
                "error": error,
                "idempotent": True,
                "belief_status": "not_committed",
            }
        actuator = organism.runtime.actuators["whatsapp.send"]
        try:
            effect = actuator.execute(service_intent(
                inbox.config,
                f"{requesting_person} via KAIROS:\n{message}",
                "explicit owner-approved person-to-person relay",
                contacts[intended_person],
            ))
            output = effect.output if isinstance(effect.output, dict) else {}
            provider = output.get("provider") if isinstance(output.get("provider"), dict) else {}
            provider_messages = provider.get("messages") if isinstance(provider.get("messages"), list) else []
            meta_message_id = str((provider_messages[0] if provider_messages else {}).get("id") or "")
            provider_http_status = int(output.get("provider_http_status") or 0)
            store.complete_whatsapp_relay(
                request_event_id, provider_http_status, meta_message_id
            )
        except Exception as exc:
            provider_status = exc.status_code if isinstance(exc, WhatsAppTransportError) else None
            store.fail_whatsapp_relay(request_event_id, type(exc).__name__, provider_status)
            raise
        logger.info(
            "WhatsApp relay accepted requester=%s recipient=%s provider_http_status=%s message_ref=%s",
            requesting_person,
            intended_person,
            provider_http_status,
            _event_ref(meta_message_id),
        )
        return {
            "status": "accepted",
            "requesting_participant": requesting_person,
            "intended_recipient": intended_person,
            "provider_http_status": provider_http_status,
            "provider_message_id": meta_message_id,
            "delivery_status": "pending",
            "idempotent": False,
            "instruction": f"Reply briefly that the message was sent to {intended_person}.",
            "belief_status": "not_committed",
        }

    organism.cognition.tool_registry.relay_sender = send_allowed_relay
    app = FastAPI(title="Sovereign Fixpoint Organism", docs_url=None, redoc_url=None)
    stop = asyncio.Event()
    cognition_lock = threading.Lock()
    tool_capabilities = tuple(getattr(organism.cognition.tool_registry, "capabilities", ("whatsapp.send",)))
    tool_state_version = hashlib.sha256("\n".join(tool_capabilities).encode()).hexdigest()

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
            tool_state_version=tool_state_version,
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
            with cognition_lock:
                effect = organism.think()
            pending_learning_count = len(organism._pending_learning)

            def observe_sleep_phase(phase: RuntimePhase, phase_payload: Mapping[str, Any]) -> None:
                telemetry.emit(
                    "SLEEP_PHASE",
                    {
                        "event_ref": structural["event_ref"],
                        "phase": phase.value,
                        "learning_proposal_count": pending_learning_count,
                        **dict(phase_payload),
                    },
                    session_id=session_id,
                    memory_version=(
                        organism.runtime.memory[-1].commit_id if organism.runtime.memory else "genesis"
                    ),
                )

            commit = organism.sleep(observe_sleep_phase)
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

    async def experiment_observer() -> None:
        seen: dict[str, tuple[Any, ...]] = {}
        while not stop.is_set():
            try:
                response = await asyncio.to_thread(knowledge.experiment_process_status, None)
                for job in response.get("jobs", []):
                    if not isinstance(job, dict) or not job.get("job_id"):
                        continue
                    signature = (
                        job.get("state"), job.get("started_at"), job.get("finished_at"),
                        job.get("exit_code"), job.get("result_sha256"),
                    )
                    job_id = str(job["job_id"])
                    if seen.get(job_id) != signature:
                        seen[job_id] = signature
                        telemetry.emit(
                            "EXPERIMENT_JOB_STATE",
                            {
                                "capability": "process.run",
                                "job_id": job.get("job_id"),
                                "operation": job.get("task"),
                                "start_time": job.get("started_at"),
                                "finish_time": job.get("finished_at"),
                                "status": job.get("state"),
                                "exit_status": job.get("exit_code"),
                                "termination_class": job.get("termination_class"),
                                "artifact_path": job.get("result_path"),
                                "artifact_sha256": job.get("result_sha256"),
                                "peak_rss_bytes": job.get("peak_rss_bytes"),
                                "runtime_seconds": job.get("runtime_seconds"),
                                "content_exported": False,
                            },
                        )
                    recipient = store.experiment_job_recipient(job_id)
                    if recipient and job.get("state") in EXPERIMENT_TERMINAL_STATES:
                        completion = experiment_completion_observation(job, recipient)
                        if store.enqueue((completion,)):
                            logger.info(
                                "experiment completion queued job_ref=%s state=%s",
                                _event_ref(job_id),
                                job.get("state"),
                            )
            except Exception as exc:
                logger.warning("experiment observer unavailable error_type=%s", type(exc).__name__)
            await asyncio.sleep(10)

    @app.on_event("startup")
    async def start() -> None:
        app.state.worker = asyncio.create_task(worker())
        app.state.clock = asyncio.create_task(clock())
        app.state.experiment_observer = (
            asyncio.create_task(experiment_observer()) if knowledge.enabled else None
        )
        telemetry.emit(
            "SELF_STATE_OBSERVED",
            {"phase": organism.runtime.phase.value,
             "memory_commits": len(organism.runtime.memory), "capabilities": list(tool_capabilities),
             "sensor_classes": sorted({
                 "whatsapp" if item.startswith("whatsapp:") else item for item in organism.runtime.ingress.sensors
             }), "checkpoint_restored": bool(organism.identity_history)},
            memory_version=organism.runtime.memory[-1].commit_id if organism.runtime.memory else "genesis",
            tool_state_version=tool_state_version,
        )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        stop.set()
        for task in (app.state.worker, app.state.clock, getattr(app.state, "experiment_observer", None)):
            if task is not None:
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
                "experiment_observer": (
                    "running"
                    if getattr(app.state, "experiment_observer", None) is not None
                    and not app.state.experiment_observer.done()
                    else "stopped"
                ),
            },
            "ckk_knowledge": knowledge.health(),
            "capabilities": list(tool_capabilities),
            "model_tool_registry": organism.cognition.tool_registry.status(),
            "persisted_tool_invocations": store.tool_invocation_count(),
        }

    @app.post("/internal/ckk-acceptance", include_in_schema=False)
    async def ckk_acceptance(request: Request):
        authorization = request.headers.get("authorization", "")
        if not hmac.compare_digest(authorization, f"Bearer {settings.ckk_adapter_token}"):
            raise HTTPException(status_code=401, detail="unauthorized")
        prompt = (
            "Conduct a read-only CKK verification. First invoke ckk.search for op_winding. From the returned evidence, "
            "identify and invoke ckk.read on the canonical grammar source. Then invoke ckk.run for a tiny one-level "
            "FÄCHER run using canonical seed SEED_R, the registered operators, structural_identity control, and explicit "
            "small compute limits. Pin read and run to the full commit SHA returned by search. Report that commit SHA, "
            "exact source paths, and only operator names "
            "actually observed in generated provenance. Do not use prior assumptions as answers."
        )

        def execute_acceptance() -> dict[str, Any]:
            with cognition_lock:
                research = organism.cognition.research(prompt)
            trace = research["trace"]
            calls = trace["calls"]
            by_name = {item["logical_name"]: item for item in calls}
            search = by_name.get("ckk.search") or {}
            read = by_name.get("ckk.read") or {}
            run = by_name.get("ckk.run") or {}
            commits = {str(item.get("commit_sha")) for item in (search, read, run) if item.get("commit_sha")}
            passed = (
                set(by_name).issuperset({"ckk.search", "ckk.read", "ckk.run"})
                and search.get("arguments", {}).get("query") == "op_winding"
                and str(read.get("path") or "").endswith("/grammar.py")
                and bool(run.get("run_id"))
                and bool(run.get("operator_names"))
                and len(commits) == 1
                and len(next(iter(commits), "")) == 40
            )
            return {"passed": passed, **research}

        return await asyncio.to_thread(execute_acceptance)

    @app.post("/internal/research-publishing-acceptance", include_in_schema=False)
    async def research_publishing_acceptance(request: Request):
        authorization = request.headers.get("authorization", "")
        if not hmac.compare_digest(authorization, f"Bearer {settings.ckk_adapter_token}"):
            raise HTTPException(status_code=401, detail="unauthorized")
        prompt = (
            "Execute one tiny CKK FÄCHER run pinned to the current canonical commit. Use canonical seed SEED_R, "
            "all registered operators, structural_identity control, and budgets of exactly: levels 1, state_cap 100, "
            "derivation_cap 1000, wall_seconds 5, memory_mb 256. After the run completes, publish that exact run with "
            "research.publish. Do not supply an interpretation or infer operators not present in provenance."
        )

        def execute_publication_acceptance() -> dict[str, Any]:
            with cognition_lock:
                research = organism.cognition.publish_research(prompt)
            calls = research["trace"]["calls"]
            matching: tuple[dict[str, Any], dict[str, Any]] | None = None
            for run_index, run in enumerate(calls):
                if run.get("logical_name") != "ckk.run" or run.get("status") != "completed":
                    continue
                for publication in calls[run_index + 1:]:
                    if (
                        publication.get("logical_name") == "research.publish"
                        and publication.get("status") == "published"
                        and publication.get("run_id") == run.get("run_id")
                        and publication.get("commit_sha") == run.get("commit_sha")
                    ):
                        matching = (run, publication)
                        break
                if matching:
                    break
            if matching is None:
                return {"passed": False, "reason": "model did not publish its completed CKK run", **research}
            run, publication = matching
            publication_url = str(publication.get("publication_url") or "")
            passed = (
                publication_url.startswith("https://kairos.206-189-55-212.sslip.io/research/")
                and len(str(run.get("commit_sha") or "")) == 40
                and bool(run.get("operator_names"))
                and publication.get("controls_completed") is True
                and publication.get("classification") == "DIRECT"
            )
            notification: dict[str, Any] = {"attempted": False, "accepted": False}
            if passed:
                text = f"COMPLETED GENERATED RUN\n{publication_url}"
                try:
                    actuator = organism.runtime.actuators["whatsapp.send"]
                    effect = actuator.execute(service_intent(
                        organism.cognition.whatsapp, text, "notify owner of completed published CKK run"
                    ))
                    output = effect.output if isinstance(effect.output, dict) else {}
                    provider = output.get("provider") if isinstance(output.get("provider"), dict) else {}
                    notification = {
                        "attempted": True,
                        "accepted": effect.success and not effect.simulated,
                        "provider_http_status": output.get("provider_http_status"),
                        "provider_message_count": len(provider.get("messages") or []),
                        "body_contains_only_short_verdict_and_url": text == f"COMPLETED GENERATED RUN\n{publication_url}",
                    }
                except Exception as exc:
                    notification = {
                        "attempted": True, "accepted": False, "error_type": type(exc).__name__,
                        "error": str(exc)[:300],
                    }
            passed = passed and notification.get("accepted") is True
            logger.info(
                "research publication acceptance passed=%s run_id=%s notification_status=%s",
                passed, str(run.get("run_id", ""))[:12], notification.get("provider_http_status"),
            )
            return {
                "passed": passed,
                "run_id": run.get("run_id"),
                "commit_sha": run.get("commit_sha"),
                "publication_url": publication_url,
                "operator_names": run.get("operator_names"),
                "notification": notification,
                **research,
            }

        return await asyncio.to_thread(execute_publication_acceptance)

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
            relay = store.update_whatsapp_relay_delivery(
                delivery_status.message_id, delivery_status.status, delivery_status.timestamp
            )
            if relay is not None:
                logger.info(
                    "WhatsApp relay delivery requester=%s recipient=%s status=%s message_ref=%s",
                    relay["requesting_participant"],
                    relay["intended_recipient"],
                    delivery_status.status,
                    _event_ref(delivery_status.message_id),
                )
                telemetry.emit(
                    "WHATSAPP_RELAY_DELIVERY",
                    {
                        "requesting_participant": relay["requesting_participant"],
                        "intended_recipient": relay["intended_recipient"],
                        "status": delivery_status.status,
                        "provider_timestamp": delivery_status.timestamp,
                        "provider_message_ref": _event_ref(delivery_status.message_id),
                        "content_exported": False,
                        "phone_identifiers_exported": False,
                    },
                )
        return {"status": "queued", "admitted": admitted, "duplicates": len(observations) - admitted}

    return app
