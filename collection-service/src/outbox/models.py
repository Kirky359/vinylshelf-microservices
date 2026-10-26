SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    saga_id TEXT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',   -- new | sent | failed
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    next_attempt_at REAL NOT NULL DEFAULT 0
);
"""
