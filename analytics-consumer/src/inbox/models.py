SCHEMA = """CREATE TABLE IF NOT EXISTS inbox (
    message_id TEXT PRIMARY KEY, saga_id TEXT, event TEXT, payload TEXT NOT NULL,
    status TEXT NOT NULL,              -- processed | failed
    deliveries INTEGER NOT NULL DEFAULT 1, received_at TEXT NOT NULL)"""
