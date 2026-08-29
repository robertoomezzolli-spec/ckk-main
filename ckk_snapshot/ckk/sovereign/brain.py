"""OpenAI Responses API cognition adapter.

The model receives observations and committed context, but never an actuator.
Its structured output is translated into a bounded Intent by trusted code.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Callable, Protocol

from .learning import LearningProposal
from .organism import BootstrapLaws, CognitionResult
from .runtime import Intent, MemoryCommit, Observation
from .whatsapp import WhatsAppConfig, service_intent, template_intent


class ResponsesClient(Protocol):
    responses: Any


DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["silence", "service_message", "template_message"]},
        "text": {"type": ["string", "null"]},
        "template": {"type": ["string", "null"]},
        "reason": {"type": "string"},
        "salience": {"type": "number", "minimum": 0, "maximum": 1},
        "learning": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["key", "value", "confidence", "evidence_ids", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["action", "text", "template", "reason", "salience", "learning"],
    "additionalProperties": False,
}


@dataclass
class OpenAIResponsesCognition:
    """A brain without a seeded name, persona, language or obligation to reply."""

    whatsapp: WhatsAppConfig
    client: ResponsesClient | None = None
    model: str = "gpt-5.6"
    history_provider: Callable[[int], list[dict[str, Any]]] = lambda limit: []
    service_window_provider: Callable[[str | None], bool] = lambda recipient: False
    history_limit: int = 24

    def __post_init__(self) -> None:
        if self.client is None:
            from openai import OpenAI

            self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def reflect(
        self,
        observations: tuple[Observation, ...],
        memory: tuple[MemoryCommit, ...],
        learned_context: dict,
        laws: BootstrapLaws,
    ) -> CognitionResult:
        current_ids = {item.observation_id for item in observations}
        direct_sensors = {
            item.sensor
            for item in observations
            if item.sensor.startswith("whatsapp:") and item.kind.startswith("message.")
        }
        if len(direct_sensors) > 1:
            raise ValueError("one cognition cycle cannot mix WhatsApp senders")
        direct_sensor = next(iter(direct_sensors), None)
        reply_to = direct_sensor.removeprefix("whatsapp:") if direct_sensor else None
        service_available = bool(self.service_window_provider(reply_to))
        direct_message = direct_sensor is not None
        recent_episodes = self.history_provider(max(self.history_limit, 1000))
        if direct_sensor:
            recent_episodes = [
                episode
                for episode in recent_episodes
                if str((episode.get("observation") or {}).get("sensor", "")) == direct_sensor
            ]
        recent_episodes = recent_episodes[-self.history_limit :]
        payload = {
            "immutable_laws": asdict(laws),
            "committed_beliefs": learned_context,
            "recent_episodes": recent_episodes,
            "current_observations": [asdict(item) for item in observations],
            "memory_head": asdict(memory[-1]) if memory else None,
            "available_outputs": {
                "service_message": {"available": service_available},
                "template_message": sorted(self.whatsapp.allowed_templates),
                "silence": "always valid",
            },
            "conversation_policy": {
                "direct_message_present": direct_message,
                "direct_message_reply_required": direct_message and service_available,
            },
        }
        decision_schema = deepcopy(DECISION_SCHEMA)
        if direct_message and service_available:
            decision_schema["properties"]["action"]["enum"] = ["service_message"]
        instructions = (
            "You are the cognition process inside a persistent bounded organism. "
            "No name, persona, language, ideology, reply duty, or preference has been assigned to you. "
            "Infer meaning from evidence and committed history. "
            "When a current observation is a direct inbound WhatsApp message and service_message is available, "
            "answer that message with a useful service_message in the sender's language. "
            "You may remain silent for clock ticks or when no safe response channel is available. "
            "Never claim an action occurred; only propose one structured decision. "
            "Learning must cite only current observation IDs and must describe durable meaning, not capabilities, "
            "safety policy, recipients, grammar, or actuators. Do not invent evidence IDs."
        )
        assert self.client is not None
        response = self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "sovereign_cognition_decision",
                    "schema": decision_schema,
                    "strict": True,
                }
            },
        )
        raw = json.loads(response.output_text)
        if direct_message and service_available and raw.get("action") != "service_message":
            raise ValueError("direct inbound WhatsApp message requires a service reply")
        proposals = tuple(self._proposal(item, current_ids) for item in raw["learning"])
        intent = self._intent(raw, reply_to)
        return CognitionResult(intent=intent, learning=proposals, salience=float(raw["salience"]))

    def _proposal(self, raw: dict[str, Any], current_ids: set[str]) -> LearningProposal:
        evidence = tuple(str(item) for item in raw["evidence_ids"])
        if not evidence or not set(evidence).issubset(current_ids):
            raise PermissionError("brain proposed learning without current evidence")
        return LearningProposal(
            key=str(raw["key"]),
            value=str(raw["value"]),
            confidence=float(raw["confidence"]),
            evidence_ids=evidence,
            reason=str(raw["reason"]),
        )

    def _intent(self, raw: dict[str, Any], reply_to: str | None = None) -> Intent | None:
        action = raw["action"]
        reason = str(raw["reason"])
        if action == "silence":
            return None
        if action == "service_message":
            text = str(raw.get("text") or "").strip()
            if not text:
                raise ValueError("service_message requires text")
            return service_intent(self.whatsapp, text, reason, reply_to)
        if action == "template_message":
            template = str(raw.get("template") or "").strip()
            if template not in self.whatsapp.allowed_templates:
                raise PermissionError("brain selected an unregistered template")
            return template_intent(self.whatsapp, template, reason)
        raise ValueError("unknown cognition action")
