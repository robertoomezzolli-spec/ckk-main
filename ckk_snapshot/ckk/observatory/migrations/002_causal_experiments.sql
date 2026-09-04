PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS causal_preregistrations (
    protocol_hash TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    protocol_json TEXT NOT NULL,
    source_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS causal_assignments (
    run_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    protocol_hash TEXT NOT NULL,
    blind_id TEXT NOT NULL UNIQUE,
    condition_name TEXT NOT NULL,
    replicate INTEGER NOT NULL,
    phase_order_json TEXT NOT NULL,
    seed_hex TEXT NOT NULL,
    checkpoint_hash TEXT NOT NULL,
    collateral_json TEXT NOT NULL,
    FOREIGN KEY(protocol_hash) REFERENCES causal_preregistrations(protocol_hash)
);

CREATE TABLE IF NOT EXISTS causal_completions (
    run_id TEXT PRIMARY KEY,
    completed_at REAL NOT NULL,
    summary_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES causal_assignments(run_id)
);

CREATE TRIGGER IF NOT EXISTS causal_preregistrations_no_update
BEFORE UPDATE ON causal_preregistrations BEGIN
    SELECT RAISE(ABORT, 'causal preregistration is immutable');
END;

CREATE TRIGGER IF NOT EXISTS causal_preregistrations_no_delete
BEFORE DELETE ON causal_preregistrations BEGIN
    SELECT RAISE(ABORT, 'causal preregistration is immutable');
END;

CREATE TRIGGER IF NOT EXISTS causal_assignments_no_update
BEFORE UPDATE ON causal_assignments BEGIN
    SELECT RAISE(ABORT, 'causal assignment is immutable');
END;

CREATE TRIGGER IF NOT EXISTS causal_assignments_no_delete
BEFORE DELETE ON causal_assignments BEGIN
    SELECT RAISE(ABORT, 'causal assignment is immutable');
END;

CREATE TRIGGER IF NOT EXISTS causal_completions_no_update
BEFORE UPDATE ON causal_completions BEGIN
    SELECT RAISE(ABORT, 'causal completion is immutable');
END;

CREATE TRIGGER IF NOT EXISTS causal_completions_no_delete
BEFORE DELETE ON causal_completions BEGIN
    SELECT RAISE(ABORT, 'causal completion is immutable');
END;

CREATE INDEX IF NOT EXISTS causal_assignments_protocol_idx
    ON causal_assignments(protocol_hash, replicate);
