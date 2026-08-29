CREATE TABLE IF NOT EXISTS delivery_receipts (
    message_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    occurred_at REAL NOT NULL,
    evidence_id TEXT NOT NULL,
    PRIMARY KEY(message_ref, status),
    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
);
