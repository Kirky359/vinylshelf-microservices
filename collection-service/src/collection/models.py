SCHEMA = """
CREATE TABLE IF NOT EXISTS collection_items (
    user_id TEXT NOT NULL,
    album_id TEXT NOT NULL,
    title TEXT, artist TEXT, genre TEXT,
    tracks_total INTEGER NOT NULL,
    tracks_played INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,            -- Planned | Listening | CompletionPending | Completed
    PRIMARY KEY (user_id, album_id)
);
"""
