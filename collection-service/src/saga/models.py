SCHEMA = """
CREATE TABLE IF NOT EXISTS saga_log (
    saga_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    album_id TEXT NOT NULL,
    prev_status TEXT NOT NULL,
    state TEXT NOT NULL,             -- started | sent | processed | compensated
    reason TEXT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
