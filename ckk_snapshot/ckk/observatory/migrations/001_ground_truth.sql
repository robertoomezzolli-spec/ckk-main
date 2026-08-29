PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS randomization (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    seed_hex TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trials (
    trial_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    due_at REAL NOT NULL,
    completed_at REAL,
    subject_id TEXT NOT NULL,
    probe_class TEXT NOT NULL,
    assignment TEXT NOT NULL CHECK(assignment IN ('control','intervention')),
    surface_form TEXT NOT NULL,
    synthetic_label TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    private_state_json TEXT NOT NULL,
    status TEXT NOT NULL,
    result_evidence_id TEXT
);

CREATE INDEX IF NOT EXISTS trials_due_idx ON trials(status, due_at);
