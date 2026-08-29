"""WhatsApp Cloud API boundary for a single-owner sovereign agent.

Inbound webhook events are authenticated and pinned to one WhatsApp user.
Outbound free-form messages are permitted only inside the customer-service
window; outside it, the agent may stay silent or use an explicitly admitted
template.  This module performs no network I/O in its default actuator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import json
import time
from typing import Any, Mapping, Protocol
from urllib import error, request

from .runtime import Effect, Intent, Observation


SERVICE_WINDOW_SECONDS = 24 * 60 * 60


def verify_webhook_signature(raw_body: bytes, header: str, app_secret: str) -> bool:
    if not header.startswith("sha256=") or not app_secret:
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


def verify_challenge(mode: str, token: str, challenge: str, expected_token: str) -> str:
    if mode != "subscribe" or not challenge or not expected_token or not hmac.compare_digest(token, expected_token):
        raise PermissionError("invalid webhook verification challenge")
    return challenge


@dataclass(frozen=True)
class WhatsAppConfig:
    owner_wa_id: str
    business_phone_number_id: str
    allowed_templates: frozenset[str] = frozenset()
    maximum_proactive_per_day: int = 3
    template_language_code: str = "en_US"


@dataclass(frozen=True)
class WhatsAppDeliveryStatus:
    """Non-secret delivery receipt metadata emitted by Meta."""

    message_id: str
    status: str
    timestamp: int


def extract_delivery_statuses(raw_body: bytes) -> tuple[WhatsAppDeliveryStatus, ...]:
    """Extract outbound delivery receipts without admitting them as messages."""

    payload = json.loads(raw_body)
    statuses = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for status in change.get("value", {}).get("statuses", []):
                message_id = str(status.get("id", ""))
                state = str(status.get("status", ""))
                timestamp = int(status.get("timestamp", "0"))
                if message_id and state and timestamp > 0:
                    statuses.append(WhatsAppDeliveryStatus(message_id, state, timestamp))
    return tuple(statuses)


@dataclass
class WhatsAppInbox:
    config: WhatsAppConfig
    last_owner_message_at: int | None = None

    def parse(self, raw_body: bytes, signature: str, app_secret: str) -> tuple[Observation, ...]:
        if not verify_webhook_signature(raw_body, signature, app_secret):
            raise PermissionError("invalid WhatsApp webhook signature")
        payload = json.loads(raw_body)
        if payload.get("object") != "whatsapp_business_account":
            raise ValueError("unexpected webhook object")
        observations = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                if metadata.get("phone_number_id") != self.config.business_phone_number_id:
                    raise PermissionError("webhook targets another business number")
                for message in value.get("messages", []):
                    observations.append(self._message_to_observation(message))
        return tuple(observations)

    def _message_to_observation(self, message: Mapping[str, Any]) -> Observation:
        sender = str(message.get("from", ""))
        if sender != self.config.owner_wa_id:
            raise PermissionError("sender is not the admitted owner")
        message_id = str(message.get("id", ""))
        timestamp = int(message.get("timestamp", "0"))
        if not message_id or timestamp <= 0:
            raise ValueError("message identity or timestamp missing")
        message_type = message.get("type")
        if message_type == "text":
            kind = "message.text"
            content = {"text": str(message.get("text", {}).get("body", "")), "timestamp": timestamp}
        elif message_type in {"document", "image", "audio"}:
            media = message.get(message_type, {})
            if not media.get("id"):
                raise ValueError(f"{message_type} media id missing")
            kind = f"message.{message_type}"
            content = {
                "media_id": str(media["id"]),
                "filename": str(media.get("filename", message_type)),
                "mime_type": str(media.get("mime_type", "application/octet-stream")),
                "sha256": str(media.get("sha256", "")),
                "caption": str(media.get("caption", "")),
                "voice": bool(media.get("voice", False)),
                "timestamp": timestamp,
            }
        else:
            raise ValueError(f"unsupported WhatsApp message type: {message_type}")
        self.last_owner_message_at = max(self.last_owner_message_at or 0, timestamp)
        return Observation(
            observation_id=f"wa:{message_id}",
            sensor=f"whatsapp:{sender}",
            kind=kind,
            payload=content,
            trust=1.0,
        )


@dataclass
class WhatsAppSimulationActuator:
    """Policy-complete outbox that never sends a real WhatsApp message."""

    config: WhatsAppConfig
    inbox: WhatsAppInbox
    now: callable = lambda: int(time.time())
    capability: str = "whatsapp.send"
    effects: list[Effect] = field(default_factory=list)
    proactive_timestamps: list[int] = field(default_factory=list)

    def execute(self, intent: Intent) -> Effect:
        payload = dict(intent.payload)
        if str(payload.get("to", "")) != self.config.owner_wa_id:
            raise PermissionError("outbound recipient is not the admitted owner")
        mode = str(payload.get("mode", "service"))
        current = int(self.now())
        if mode == "service":
            if self.inbox.last_owner_message_at is None:
                raise PermissionError("no customer-service window exists")
            if current - self.inbox.last_owner_message_at > SERVICE_WINDOW_SECONDS:
                raise PermissionError("free-form service window is closed")
            if not str(payload.get("text", "")).strip():
                raise ValueError("service message text is empty")
        elif mode == "template":
            template = str(payload.get("template", ""))
            if template not in self.config.allowed_templates:
                raise PermissionError("template is not admitted")
            day_ago = current - 24 * 60 * 60
            self.proactive_timestamps = [t for t in self.proactive_timestamps if t >= day_ago]
            if len(self.proactive_timestamps) >= self.config.maximum_proactive_per_day:
                raise PermissionError("proactive daily budget exhausted")
            self.proactive_timestamps.append(current)
        else:
            raise ValueError("outbound mode must be service or template")
        effect = Effect(
            intent_id=intent.intent_id,
            capability=self.capability,
            success=True,
            simulated=True,
            output={"would_send": payload, "mode": mode},
        )
        self.effects.append(effect)
        return effect


class JsonTransport(Protocol):
    def post(self, url: str, headers: Mapping[str, str], payload: Mapping[str, Any]) -> "JsonTransportResult": ...


@dataclass(frozen=True)
class JsonTransportResult:
    status_code: int
    body: Mapping[str, Any]


class WhatsAppTransportError(RuntimeError):
    def __init__(self, status_code: int, body: Mapping[str, Any]):
        self.status_code = int(status_code)
        self.body = dict(body)
        provider_error = self.body.get("error") if isinstance(self.body.get("error"), Mapping) else {}
        code = provider_error.get("code", "unknown")
        error_type = provider_error.get("type", "unknown")
        message = provider_error.get("message", "unknown provider error")
        super().__init__(f"WhatsApp Graph API HTTP {self.status_code}: {error_type} {code}: {message}")


@dataclass
class UrllibJsonTransport:
    timeout_seconds: float = 20.0

    def post(self, url: str, headers: Mapping[str, str], payload: Mapping[str, Any]) -> JsonTransportResult:
        body = json.dumps(payload, separators=(",", ":")).encode()
        req = request.Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
                parsed = json.loads(raw) if raw else {}
                if not isinstance(parsed, Mapping):
                    raise ValueError("WhatsApp Graph API returned a non-object JSON body")
                return JsonTransportResult(int(response.status), parsed)
        except error.HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"error": {"type": "non_json_response", "message": raw.decode(errors="replace")[:500]}}
            if not isinstance(parsed, Mapping):
                parsed = {"error": {"type": "non_object_response", "message": str(parsed)[:500]}}
            raise WhatsAppTransportError(exc.code, parsed) from exc


@dataclass
class WhatsAppCloudActuator(WhatsAppSimulationActuator):
    """Real Cloud API sender; all policy checks remain in the parent boundary."""

    access_token: str = ""
    graph_api_version: str = "v23.0"
    transport: JsonTransport = field(default_factory=UrllibJsonTransport)

    def execute(self, intent: Intent) -> Effect:
        checked = super().execute(intent)
        outbound = checked.output["would_send"]
        if checked.output["mode"] == "service":
            body = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": outbound["to"],
                "type": "text",
                "text": {"preview_url": False, "body": outbound["text"]},
            }
        else:
            body = {
                "messaging_product": "whatsapp",
                "to": outbound["to"],
                "type": "template",
                "template": {
                    "name": outbound["template"],
                    "language": {"code": self.config.template_language_code},
                },
            }
        if not self.access_token:
            raise RuntimeError("WhatsApp access token is missing")
        result = self.transport.post(
            f"https://graph.facebook.com/{self.graph_api_version}/{self.config.business_phone_number_id}/messages",
            {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
            body,
        )
        if not 200 <= result.status_code < 300:
            raise WhatsAppTransportError(result.status_code, result.body)
        effect = Effect(
            intent.intent_id,
            self.capability,
            True,
            False,
            {
                "provider": dict(result.body),
                "provider_http_status": result.status_code,
                "mode": checked.output["mode"],
                "sent_at": int(self.now()),
            },
        )
        self.effects[-1] = effect
        return effect


def service_intent(config: WhatsAppConfig, text: str, reason: str) -> Intent:
    return Intent(
        action="send_whatsapp",
        capability="whatsapp.send",
        payload={"to": config.owner_wa_id, "mode": "service", "text": text},
        reason=reason,
    )


def template_intent(config: WhatsAppConfig, template: str, reason: str) -> Intent:
    return Intent(
        action="send_whatsapp_template",
        capability="whatsapp.send",
        payload={"to": config.owner_wa_id, "mode": "template", "template": template},
        reason=reason,
    )
