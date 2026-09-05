"""SQLite-backed event queue, episodic memory and organism checkpoint."""

from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
import threading
from typing import Any

from .learning import Belief
from .organism import OrganismCommit, SovereignOrganism
from .runtime import AuditEvent, MemoryCommit, Observation, RuntimePhase


class SQLiteStateStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._db:
            self._db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS queue (
                    event_id TEXT PRIMARY KEY,
                    observation_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS episodes (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    episode_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checkpoint (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS external_evidence (
                    observation_id TEXT PRIMARY KEY,
                    parent_event_id TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    ref TEXT NOT NULL,
                    commit_sha TEXT NOT NULL,
                    base_commit_sha TEXT NOT NULL,
                    blob_sha TEXT NOT NULL,
                    path TEXT NOT NULL,
                    start_line INTEGER,
                    end_line INTEGER,
                    source_kind TEXT NOT NULL,
                    evidence_labels_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL
                );
                """
            )

    def enqueue(self, observations: tuple[Observation, ...]) -> int:
        admitted = 0
        with self._lock, self._db:
            for observation in observations:
                cursor = self._db.execute(
                    "INSERT OR IGNORE INTO queue(event_id, observation_json) VALUES (?, ?)",
                    (observation.observation_id, json.dumps(asdict(observation), default=str, sort_keys=True)),
                )
                admitted += cursor.rowcount
        return admitted

    def next_observation(self, maximum_attempts: int = 5) -> Observation | None:
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT * FROM queue WHERE status IN ('queued','retry') AND attempts < ? ORDER BY rowid LIMIT 1",
                (maximum_attempts,),
            ).fetchone()
            if row is None:
                return None
            self._db.execute(
                "UPDATE queue SET status='processing', attempts=attempts+1 WHERE event_id=?",
                (row["event_id"],),
            )
        return self._observation(json.loads(row["observation_json"]))

    def retry_stale(self) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE queue SET status='retry' WHERE status='processing'")

    def fail(self, event_id: str, error: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE queue SET status='retry', last_error=? WHERE event_id=?",
                (error[:1000], event_id),
            )

    def complete(self, observation: Observation, episode: dict[str, Any], organism: SovereignOrganism) -> None:
        checkpoint = self._serialize_organism(organism)
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO episodes(event_id, episode_json) VALUES (?, ?)",
                (observation.observation_id, json.dumps(episode, default=str, sort_keys=True)),
            )
            self._db.execute("UPDATE queue SET status='done', last_error=NULL WHERE event_id=?", (observation.observation_id,))
            self._db.execute(
                "INSERT INTO checkpoint(singleton, state_json) VALUES (1, ?) "
                "ON CONFLICT(singleton) DO UPDATE SET state_json=excluded.state_json",
                (json.dumps(checkpoint, default=str, sort_keys=True),),
            )

    def recent_episodes(self, limit: int = 24) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT episode_json FROM episodes ORDER BY sequence DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["episode_json"]) for row in reversed(rows)]

    def record_external_evidence(self, parent_event_id: str, observations: tuple[Observation, ...]) -> None:
        """Persist provenance only; excerpts never enter episodic context or checkpoint state."""
        with self._lock, self._db:
            for observation in observations:
                if observation.sensor != "ckk.repository" or observation.kind != "evidence.source":
                    raise ValueError("external evidence store accepts only CKK evidence observations")
                payload = observation.payload
                self._db.execute(
                    "INSERT OR IGNORE INTO external_evidence("
                    "observation_id,parent_event_id,repository,ref,commit_sha,base_commit_sha,blob_sha,path,"
                    "start_line,end_line,source_kind,evidence_labels_json,content_sha256"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        observation.observation_id, parent_event_id, str(payload["repository"]),
                        str(payload.get("ref") or ""), str(payload["commit_sha"]),
                        str(payload.get("base_commit_sha") or ""), str(payload.get("blob_sha") or ""),
                        str(payload["path"]), payload.get("start_line"), payload.get("end_line"),
                        str(payload["source_kind"]), json.dumps(payload.get("evidence_labels") or [], sort_keys=True),
                        str(payload.get("content_sha256") or ""),
                    ),
                )

    def external_evidence_count(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COUNT(*) FROM external_evidence").fetchone()
        return int(row[0])

    def communication_state(self) -> tuple[dict[str, int], list[int]]:
        """Recover service-window and proactive budget state after restart."""
        windows: dict[str, int] = {}
        proactive: list[int] = []
        for episode in self.recent_episodes(1000):
            observation = episode.get("observation") or {}
            sensor = str(observation.get("sensor", ""))
            if sensor.startswith("whatsapp:"):
                timestamp = (observation.get("payload") or {}).get("timestamp")
                if timestamp is not None:
                    sender = sensor.removeprefix("whatsapp:")
                    windows[sender] = max(windows.get(sender, 0), int(timestamp))
            output = (episode.get("effect") or {}).get("output") or {}
            if output.get("mode") == "template" and output.get("sent_at") is not None:
                proactive.append(int(output["sent_at"]))
        return windows, proactive

    def queue_stats(self) -> dict[str, int]:
        with self._lock:
            rows = self._db.execute("SELECT status, COUNT(*) AS count FROM queue GROUP BY status").fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def restore(self, organism: SovereignOrganism) -> bool:
        with self._lock:
            row = self._db.execute("SELECT state_json FROM checkpoint WHERE singleton=1").fetchone()
        if row is None:
            return False
        raw = json.loads(row["state_json"])
        organism.identity = raw["identity"]
        organism.identity_history = [OrganismCommit(**item) for item in raw["identity_history"]]
        organism.learner.head = raw["learner"]["head"]
        organism.learner.history = [
            Belief(**{**item, "evidence_ids": tuple(item["evidence_ids"])})
            for item in raw["learner"]["history"]
        ]
        organism.learner.beliefs = {item.key: item for item in organism.learner.history}
        organism.runtime.memory = [
            MemoryCommit(
                **{
                    **item,
                    "observation_ids": tuple(item["observation_ids"]),
                    "effect_ids": tuple(item["effect_ids"]),
                }
            )
            for item in raw["runtime"]["memory"]
        ]
        organism.runtime.audit.events = [AuditEvent(**item) for item in raw["runtime"]["audit_events"]]
        organism.runtime.audit.head = raw["runtime"]["audit_head"]
        organism.runtime._seen_observations = set(raw["runtime"]["seen_observations"])
        organism.runtime.phase = RuntimePhase.WAKE
        return True

    @staticmethod
    def _observation(raw: dict[str, Any]) -> Observation:
        return Observation(
            observation_id=raw["observation_id"], sensor=raw["sensor"], kind=raw["kind"],
            payload=raw["payload"], trust=float(raw["trust"])
        )

    @staticmethod
    def _serialize_organism(organism: SovereignOrganism) -> dict[str, Any]:
        return {
            "identity": organism.identity,
            "identity_history": [asdict(item) for item in organism.identity_history],
            "learner": {
                "head": organism.learner.head,
                "history": [asdict(item) for item in organism.learner.history],
            },
            "runtime": {
                "memory": [asdict(item) for item in organism.runtime.memory],
                "audit_events": [asdict(item) for item in organism.runtime.audit.events],
                "audit_head": organism.runtime.audit.head,
                "seen_observations": sorted(organism.runtime._seen_observations),
            },
        }
