PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL UNIQUE,
    occurred_at REAL NOT NULL,
    recorded_at REAL NOT NULL,
    subject_id TEXT NOT NULL,
    subject_version TEXT NOT NULL,
    session_id TEXT,
    event_type TEXT NOT NULL,
    metric TEXT,
    control_class TEXT,
    intervention_class TEXT,
    evaluator_version TEXT,
    model_version TEXT,
    memory_version TEXT,
    tool_state_version TEXT,
    confidence REAL,
    latency_ms REAL,
    payload_json TEXT NOT NULL,
    prior_hash TEXT NOT NULL,
    evidence_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS evidence_occurred_at_idx
    ON evidence(occurred_at);
CREATE INDEX IF NOT EXISTS evidence_subject_metric_idx
    ON evidence(subject_id, metric, occurred_at);
CREATE INDEX IF NOT EXISTS evidence_event_type_idx
    ON evidence(event_type, occurred_at);

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    score REAL NOT NULL CHECK(score >= 0 AND score <= 1),
    weight REAL NOT NULL CHECK(weight > 0),
    correctness INTEGER,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    expected_class TEXT,
    actual_class TEXT,
    evaluator_version TEXT NOT NULL,
    evaluated_at REAL NOT NULL,
    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);

CREATE INDEX IF NOT EXISTS evaluations_metric_idx
    ON evaluations(metric, evaluated_at);
