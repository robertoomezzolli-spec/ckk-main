#!/usr/bin/env python3
"""Import redacted structural history as pre-optimization KAIROS evidence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sqlite3
import time
from typing import Any
from urllib.request import Request, urlopen


def opaque(token: str, value: str) -> str:
    return hmac.new(token.encode(), value.encode(), hashlib.sha256).hexdigest()[:24]


def event_id(observation_id: str, event_type: str) -> str:
    return "baseline_" + hashlib.sha256(f"{observation_id}:{event_type}".encode()).hexdigest()


def occurred_at(observation: dict[str, Any]) -> float:
    payload = observation.get("payload") or {}
    return float(payload.get("timestamp") or payload.get("unix_time") or time.time())


def structural_observation(observation: dict[str, Any], token: str) -> dict[str, Any]:
    payload = observation.get("payload") or {}
    sensor = str(observation.get("sensor", "unknown"))
    result: dict[str, Any] = {
        "event_ref": opaque(token, str(observation.get("observation_id", ""))),
        "sensor_class": "whatsapp" if sensor.startswith("whatsapp:") else sensor,
        "kind": str(observation.get("kind", "unknown")),
        "trust": float(observation.get("trust", 0)),
        "payload_keys": sorted(str(key) for key in payload),
        "payload_bytes": len(json.dumps(payload, sort_keys=True, default=str).encode()),
        "historical_baseline": True,
    }
    if sensor.startswith("whatsapp:"):
        result["conversation_ref"] = opaque(token, sensor)
    if isinstance(payload.get("text"), str):
        result["text_length"] = len(payload["text"])
        result["text_digest"] = opaque(token, payload["text"])
    return result


def load_events(database_path: str, token: str, subject_version: str, model_version: str) -> list[dict[str, Any]]:
    database = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    rows = database.execute("SELECT event_id, episode_json FROM episodes ORDER BY sequence").fetchall()
    database.close()
    events: list[dict[str, Any]] = []
    prior_identity = "0" * 64
    tool_version = hashlib.sha256(b"whatsapp.send").hexdigest()
    for source_event_id, encoded in rows:
        episode = json.loads(encoded)
        observation = episode.get("observation") or {}
        commit = episode.get("commit") or {}
        effect = episode.get("effect")
        timestamp = occurred_at(observation)
        sensor = str(observation.get("sensor", ""))
        session_id = opaque(token, sensor) if sensor.startswith("whatsapp:") else None
        common = {
            "subject_id": "KAIROS-production", "subject_version": subject_version,
            "occurred_at": timestamp, "session_id": session_id, "model_version": model_version,
            "tool_state_version": tool_version,
        }
        events.append({
            **common, "evidence_id": event_id(source_event_id, "OBSERVED"), "event_type": "OBSERVED",
            "memory_version": str(commit.get("runtime_commit") or "unknown"),
            "payload": structural_observation(observation, token),
        })
        if effect:
            output = effect.get("output") or {}
            provider = output.get("provider") if isinstance(output.get("provider"), dict) else {}
            events.append({
                **common, "evidence_id": event_id(source_event_id, "ACTED"), "event_type": "ACTED",
                "memory_version": str(commit.get("runtime_commit") or "unknown"),
                "payload": {
                    "event_ref": opaque(token, source_event_id), "capability": effect.get("capability"),
                    "success": bool(effect.get("success")), "simulated": bool(effect.get("simulated")),
                    "provider_http_status": output.get("provider_http_status"),
                    "provider_message_count": len(provider.get("messages") or []),
                    "historical_baseline": True,
                },
            })
        continuity = commit.get("previous_identity") == prior_identity
        prior_identity = str(commit.get("identity") or prior_identity)
        events.append({
            **common, "evidence_id": event_id(source_event_id, "CONSOLIDATED"), "event_type": "CONSOLIDATED",
            "memory_version": str(commit.get("runtime_commit") or "unknown"),
            "payload": {
                "event_ref": opaque(token, source_event_id), "identity_chain_valid": continuity,
                "memory_advanced": bool(commit.get("runtime_commit")), "checkpoint_persisted": True,
                "sleep_cycle": "NREM_REM_WAKE", "historical_baseline": True,
            },
        })
    return events


def post_batches(url: str, token: str, events: list[dict[str, Any]]) -> int:
    accepted = 0
    for offset in range(0, len(events), 100):
        batch = events[offset : offset + 100]
        request = Request(
            url, data=json.dumps(batch, separators=(",", ":")).encode(), method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read())
            accepted += int(result["accepted"])
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--subject-version", required=True)
    parser.add_argument("--model-version", required=True)
    args = parser.parse_args()
    events = load_events(args.database, args.token, args.subject_version, args.model_version)
    count = post_batches(args.url, args.token, events)
    print(f"redacted baseline evidence accepted: {count}")


if __name__ == "__main__":
    main()
