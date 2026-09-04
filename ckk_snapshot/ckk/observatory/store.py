"""Append-only evidence and physically isolated hidden-ground-truth stores."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from importlib import resources
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from typing import Any, Iterable

from .metrics import METRIC_BY_CODE, reconstruct_scores


EVALUATOR_VERSION = "awareness-observatory-v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class EvidenceEvent:
    event_type: str
    subject_id: str
    subject_version: str = "unknown"
    occurred_at: float = 0.0
    session_id: str | None = None
    metric: str | None = None
    control_class: str | None = None
    intervention_class: str | None = None
    evaluator_version: str | None = None
    model_version: str | None = None
    memory_version: str | None = None
    tool_state_version: str | None = None
    confidence: float | None = None
    latency_ms: float | None = None
    payload: dict[str, Any] | None = None
    evidence_id: str | None = None


class ObservatoryStore:
    """Owns two SQLite files; neither file is mounted into the organism."""

    def __init__(self, directory: str):
        os.makedirs(directory, exist_ok=True)
        self.directory = os.path.abspath(directory)
        self.evidence_path = os.path.join(self.directory, "evidence.sqlite3")
        self.ground_truth_path = os.path.join(self.directory, "ground_truth.sqlite3")
        self._lock = threading.RLock()
        self._evidence = sqlite3.connect(self.evidence_path, check_same_thread=False)
        self._truth = sqlite3.connect(self.ground_truth_path, check_same_thread=False)
        self._evidence.row_factory = sqlite3.Row
        self._truth.row_factory = sqlite3.Row
        self._migrate(self._evidence, ((1, "001_evidence.sql"), (2, "002_delivery.sql")))
        self._migrate(
            self._truth,
            ((1, "001_ground_truth.sql"), (2, "002_causal_experiments.sql")),
        )
        with self._truth:
            self._truth.execute(
                "INSERT OR IGNORE INTO randomization(singleton, seed_hex, created_at) VALUES(1, ?, ?)",
                (secrets.token_hex(32), time.time()),
            )

    @staticmethod
    def _migrate(connection: sqlite3.Connection, migrations: Iterable[tuple[int, str]]) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)"
        )
        applied = {int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")}
        migration_root = resources.files("ckk.observatory.migrations")
        for version, filename in migrations:
            if version in applied:
                continue
            sql = migration_root.joinpath(filename).read_text(encoding="utf-8")
            with connection:
                connection.executescript(sql)
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                    (version, time.time()),
                )

    def close(self) -> None:
        with self._lock:
            self._evidence.close()
            self._truth.close()

    def append(self, event: EvidenceEvent) -> str:
        occurred_at = event.occurred_at or time.time()
        recorded_at = time.time()
        evidence_id = event.evidence_id or f"ev_{uuid.uuid4().hex}"
        payload = event.payload or {}
        if event.metric is not None and event.metric not in METRIC_BY_CODE:
            raise ValueError(f"unknown metric: {event.metric}")
        if event.confidence is not None and not 0 <= event.confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        with self._lock, self._evidence:
            existing = self._evidence.execute(
                "SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)
            ).fetchone()
            if existing is not None:
                comparable = {
                    "event_type": event.event_type, "subject_id": event.subject_id,
                    "subject_version": event.subject_version, "session_id": event.session_id,
                    "metric": event.metric, "model_version": event.model_version,
                    "memory_version": event.memory_version, "tool_state_version": event.tool_state_version,
                    "payload_json": _canonical(payload),
                }
                if any(existing[key] != value for key, value in comparable.items()):
                    raise ValueError("evidence ID reused with different observable content")
                return evidence_id
            prior = self._evidence.execute(
                "SELECT evidence_hash FROM evidence ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            prior_hash = str(prior[0]) if prior else "0" * 64
            material = {
                **asdict(event),
                "evidence_id": evidence_id,
                "occurred_at": occurred_at,
                "recorded_at": recorded_at,
                "payload": payload,
                "prior_hash": prior_hash,
            }
            evidence_hash = hashlib.sha256(_canonical(material).encode()).hexdigest()
            self._evidence.execute(
                """INSERT INTO evidence(
                    evidence_id, occurred_at, recorded_at, subject_id, subject_version,
                    session_id, event_type, metric, control_class, intervention_class,
                    evaluator_version, model_version, memory_version, tool_state_version,
                    confidence, latency_ms, payload_json, prior_hash, evidence_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    evidence_id, occurred_at, recorded_at, event.subject_id, event.subject_version,
                    event.session_id, event.event_type, event.metric, event.control_class,
                    event.intervention_class, event.evaluator_version, event.model_version,
                    event.memory_version, event.tool_state_version, event.confidence,
                    event.latency_ms, _canonical(payload), prior_hash, evidence_hash,
                ),
            )
        return evidence_id

    def evaluate(
        self,
        evidence_id: str,
        metric: str,
        score: float,
        *,
        weight: float = 1.0,
        correctness: bool | None = None,
        confidence: float = 1.0,
        expected_class: str | None = None,
        actual_class: str | None = None,
        evaluator_version: str = EVALUATOR_VERSION,
    ) -> str:
        if metric not in METRIC_BY_CODE:
            raise ValueError(f"unknown metric: {metric}")
        if not 0 <= score <= 1 or weight <= 0 or not 0 <= confidence <= 1:
            raise ValueError("invalid evaluation range")
        evaluation_id = f"eval_{uuid.uuid4().hex}"
        with self._lock, self._evidence:
            self._evidence.execute(
                """INSERT INTO evaluations(
                    evaluation_id, evidence_id, metric, score, weight, correctness,
                    confidence, expected_class, actual_class, evaluator_version, evaluated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    evaluation_id, evidence_id, metric, score, weight,
                    None if correctness is None else int(correctness), confidence,
                    expected_class, actual_class, evaluator_version, time.time(),
                ),
            )
        return evaluation_id

    def verify_chain(self) -> tuple[bool, int]:
        with self._lock:
            rows = self._evidence.execute("SELECT * FROM evidence ORDER BY sequence").fetchall()
        prior_hash = "0" * 64
        for row in rows:
            event = {
                "event_type": row["event_type"], "subject_id": row["subject_id"],
                "subject_version": row["subject_version"], "occurred_at": row["occurred_at"],
                "session_id": row["session_id"], "metric": row["metric"],
                "control_class": row["control_class"], "intervention_class": row["intervention_class"],
                "evaluator_version": row["evaluator_version"], "model_version": row["model_version"],
                "memory_version": row["memory_version"], "tool_state_version": row["tool_state_version"],
                "confidence": row["confidence"], "latency_ms": row["latency_ms"],
                "payload": json.loads(row["payload_json"]), "evidence_id": row["evidence_id"],
                "recorded_at": row["recorded_at"], "prior_hash": prior_hash,
            }
            digest = hashlib.sha256(_canonical(event).encode()).hexdigest()
            if row["prior_hash"] != prior_hash or row["evidence_hash"] != digest:
                return False, int(row["sequence"])
            prior_hash = digest
        return True, len(rows)

    def evidence(self, *, subject_id: str | None = None, since: float | None = None, limit: int = 200) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if subject_id:
            clauses.append("subject_id=?")
            parameters.append(subject_id)
        if since is not None:
            clauses.append("occurred_at>=?")
            parameters.append(since)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        parameters.append(max(1, min(limit, 1000)))
        with self._lock:
            rows = self._evidence.execute(
                "SELECT * FROM evidence" + where + " ORDER BY sequence DESC LIMIT ?", parameters
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def evaluations(self, subject_id: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT v.*, e.subject_id, e.occurred_at
                 FROM evaluations v JOIN evidence e ON e.evidence_id=v.evidence_id"""
        parameters: tuple[Any, ...] = ()
        if subject_id:
            sql += " WHERE e.subject_id=?"
            parameters = (subject_id,)
        with self._lock:
            return [dict(row) for row in self._evidence.execute(sql, parameters).fetchall()]

    def scores(self, subject_id: str, window: str = "24h") -> dict[str, Any]:
        return reconstruct_scores(self.evaluations(subject_id), window)

    def randomization_seed(self) -> bytes:
        with self._lock:
            row = self._truth.execute("SELECT seed_hex FROM randomization WHERE singleton=1").fetchone()
        assert row is not None
        return bytes.fromhex(str(row[0]))

    def create_trial(self, trial: dict[str, Any]) -> None:
        with self._lock, self._truth:
            self._truth.execute(
                """INSERT INTO trials(
                    trial_id, created_at, due_at, subject_id, probe_class, assignment,
                    surface_form, synthetic_label, expected_json, private_state_json, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    trial["trial_id"], trial["created_at"], trial["due_at"], trial["subject_id"],
                    trial["probe_class"], trial["assignment"], trial["surface_form"],
                    trial["synthetic_label"], _canonical(trial["expected"]),
                    _canonical(trial["private_state"]), trial.get("status", "scheduled"),
                ),
            )

    def register_causal_preregistration(
        self,
        protocol_hash: str,
        protocol: dict[str, Any],
        source_hash: str,
    ) -> None:
        """Freeze a causal protocol before any assigned fork is executed.

        The database rejects replacement, update and deletion. Repeating the
        exact same registration is idempotent; a changed protocol must receive
        a new hash and therefore remains an auditable new preregistration.
        """

        encoded = _canonical(protocol)
        with self._lock, self._truth:
            existing = self._truth.execute(
                "SELECT protocol_json, source_hash FROM causal_preregistrations WHERE protocol_hash=?",
                (protocol_hash,),
            ).fetchone()
            if existing is not None:
                if existing["protocol_json"] != encoded or existing["source_hash"] != source_hash:
                    raise ValueError("causal protocol hash reused with different preregistration")
                return
            self._truth.execute(
                """INSERT INTO causal_preregistrations(
                    protocol_hash, created_at, protocol_json, source_hash
                ) VALUES(?,?,?,?)""",
                (protocol_hash, time.time(), encoded, source_hash),
            )

    def register_causal_assignment(self, assignment: dict[str, Any]) -> None:
        """Store the blinded arm mapping and hidden randomization material."""

        with self._lock, self._truth:
            existing = self._truth.execute(
                "SELECT * FROM causal_assignments WHERE run_id=?", (assignment["run_id"],)
            ).fetchone()
            if existing is not None:
                comparable = {
                    "protocol_hash": assignment["protocol_hash"],
                    "blind_id": assignment["blind_id"],
                    "condition_name": assignment["condition_name"],
                    "replicate": int(assignment["replicate"]),
                    "phase_order_json": _canonical(assignment["phase_order"]),
                    "seed_hex": assignment["seed_hex"],
                    "checkpoint_hash": assignment["checkpoint_hash"],
                    "collateral_json": _canonical(assignment.get("collateral", {})),
                }
                if any(existing[key] != value for key, value in comparable.items()):
                    raise ValueError("causal run ID reused with a different hidden assignment")
                return
            self._truth.execute(
                """INSERT INTO causal_assignments(
                    run_id, created_at, protocol_hash, blind_id, condition_name,
                    replicate, phase_order_json, seed_hex, checkpoint_hash,
                    collateral_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    assignment["run_id"], assignment.get("created_at", time.time()),
                    assignment["protocol_hash"], assignment["blind_id"],
                    assignment["condition_name"], int(assignment["replicate"]),
                    _canonical(assignment["phase_order"]), assignment["seed_hex"],
                    assignment["checkpoint_hash"],
                    _canonical(assignment.get("collateral", {})),
                ),
            )

    def complete_causal_assignment(self, run_id: str, summary: dict[str, Any]) -> None:
        """Append one terminal completion record; it cannot be rewritten."""

        encoded = _canonical(summary)
        with self._lock, self._truth:
            existing = self._truth.execute(
                "SELECT summary_json FROM causal_completions WHERE run_id=?", (run_id,)
            ).fetchone()
            if existing is not None:
                if existing["summary_json"] != encoded:
                    raise ValueError("causal completion cannot be replaced")
                return
            self._truth.execute(
                """INSERT INTO causal_completions(run_id, completed_at, summary_json)
                   VALUES(?,?,?)""",
                (run_id, time.time(), encoded),
            )

    def causal_preregistration(self, protocol_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._truth.execute(
                "SELECT * FROM causal_preregistrations WHERE protocol_hash=?", (protocol_hash,)
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["protocol"] = json.loads(item.pop("protocol_json"))
        return item

    def causal_assignments(self, protocol_hash: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._truth.execute(
                """SELECT a.*, c.completed_at, c.summary_json
                   FROM causal_assignments a
                   LEFT JOIN causal_completions c ON c.run_id=a.run_id
                   WHERE a.protocol_hash=? ORDER BY a.replicate, a.blind_id""",
                (protocol_hash,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["phase_order"] = json.loads(item.pop("phase_order_json"))
            item["collateral"] = json.loads(item.pop("collateral_json"))
            raw_summary = item.pop("summary_json")
            item["summary"] = json.loads(raw_summary) if raw_summary else None
            result.append(item)
        return result

    def due_trials(self, now: float | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._truth.execute(
                "SELECT * FROM trials WHERE status='scheduled' AND due_at<=? ORDER BY due_at",
                (time.time() if now is None else now,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["expected"] = json.loads(item.pop("expected_json"))
            item["private_state"] = json.loads(item.pop("private_state_json"))
            result.append(item)
        return result

    def complete_trial(self, trial_id: str, evidence_id: str) -> None:
        with self._lock, self._truth:
            self._truth.execute(
                "UPDATE trials SET status='completed', completed_at=?, result_evidence_id=? WHERE trial_id=?",
                (time.time(), evidence_id, trial_id),
            )

    def stats(self) -> dict[str, Any]:
        valid, count = self.verify_chain()
        with self._lock:
            trials = self._truth.execute("SELECT assignment,status,COUNT(*) count FROM trials GROUP BY assignment,status").fetchall()
        return {"chain_valid": valid, "evidence_count": count, "trials": [dict(row) for row in trials]}
