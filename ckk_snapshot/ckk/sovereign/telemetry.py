"""One-way, fail-open export of observable outcomes.

This module knows nothing about Observatory storage, probes, scoring, ground
truth, or schedules.  It deliberately exports no message bodies, phone
numbers, model instructions, secrets, or private reasoning traces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import logging
from queue import Empty, Full, Queue
import threading
import time
from typing import Any, Protocol
from urllib.request import Request, urlopen
import uuid

from .runtime import Observation


logger = logging.getLogger("uvicorn.error")


class TelemetrySink(Protocol):
    def emit(self, event_type: str, payload: dict[str, Any], **metadata: Any) -> None: ...
    def close(self) -> None: ...


@dataclass
class NullTelemetrySink:
    def emit(self, event_type: str, payload: dict[str, Any], **metadata: Any) -> None:
        return None

    def close(self) -> None:
        return None


@dataclass
class RecordingTelemetrySink:
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, payload: dict[str, Any], **metadata: Any) -> None:
        self.events.append({"event_type": event_type, "payload": payload, **metadata})

    def close(self) -> None:
        return None


class HttpTelemetrySink:
    """Bounded asynchronous delivery so observation cannot block cognition."""

    def __init__(self, url: str, token: str, subject_version: str, model_version: str, queue_size: int = 1024):
        if not url or not token:
            raise ValueError("telemetry URL and token are both required")
        self.url = url
        self._token = token
        self.subject_version = subject_version
        self.model_version = model_version
        self._queue: Queue[dict[str, Any] | None] = Queue(maxsize=queue_size)
        self._thread = threading.Thread(target=self._deliver, name="observable-outcomes", daemon=True)
        self._thread.start()

    def opaque_ref(self, value: str) -> str:
        return hmac.new(self._token.encode(), value.encode(), hashlib.sha256).hexdigest()[:24]

    def emit(self, event_type: str, payload: dict[str, Any], **metadata: Any) -> None:
        event = {
            "evidence_id": f"src_{uuid.uuid4().hex}",
            "event_type": event_type,
            "subject_id": "KAIROS-production",
            "subject_version": self.subject_version,
            "model_version": self.model_version,
            "occurred_at": time.time(),
            "payload": payload,
            **metadata,
        }
        try:
            self._queue.put_nowait(event)
        except Full:
            logger.warning("observable outcome queue full; telemetry event dropped type=%s", event_type)

    def _deliver(self) -> None:
        while True:
            try:
                event = self._queue.get(timeout=0.5)
            except Empty:
                continue
            if event is None:
                self._queue.task_done()
                return
            try:
                body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
                request = Request(
                    self.url, data=body, method="POST",
                    headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                )
                with urlopen(request, timeout=2.0) as response:
                    if response.status != 202:
                        logger.warning("observable outcome rejected status=%s", response.status)
            except Exception as exc:
                logger.warning("observable outcome delivery failed error_type=%s", type(exc).__name__)
            finally:
                self._queue.task_done()

    def close(self) -> None:
        try:
            self._queue.put_nowait(None)
        except Full:
            return
        self._thread.join(timeout=3.0)


def sanitized_observation(observation: Observation, opaque_ref=lambda value: hashlib.sha256(value.encode()).hexdigest()[:24]) -> dict[str, Any]:
    """Reduce an observation to structural metadata without user content or IDs."""

    sensor_class = "whatsapp" if observation.sensor.startswith("whatsapp:") else observation.sensor
    payload = dict(observation.payload)
    structure: dict[str, Any] = {
        "event_ref": opaque_ref(observation.observation_id),
        "sensor_class": sensor_class,
        "kind": observation.kind,
        "trust": observation.trust,
        "payload_keys": sorted(str(key) for key in payload),
        "payload_bytes": len(json.dumps(payload, sort_keys=True, default=str).encode()),
    }
    if observation.sensor.startswith("whatsapp:"):
        structure["conversation_ref"] = opaque_ref(observation.sensor)
    if isinstance(payload.get("text"), str):
        structure["text_length"] = len(payload["text"])
        structure["text_digest"] = opaque_ref(payload["text"])
    return structure
