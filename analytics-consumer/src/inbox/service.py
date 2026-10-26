"""Transactional Inbox: every received message_id is stored, so a redelivered message is recognised as a duplicate."""
import json
import os
import sqlite3
from datetime import datetime, timezone

from src.config import settings
from src.inbox.models import SCHEMA


def init() -> None:
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    with sqlite3.connect(settings.db_path) as c:
        c.execute(SCHEMA)


def get(message_id):
    with sqlite3.connect(settings.db_path) as c:
        return c.execute("SELECT status FROM inbox WHERE message_id=?", (message_id,)).fetchone()


def save(event: dict, status: str) -> None:
    with sqlite3.connect(settings.db_path) as c:
        c.execute("INSERT OR REPLACE INTO inbox (message_id,saga_id,event,payload,status,received_at) VALUES (?,?,?,?,?,?)",
                  (event["message_id"], event.get("saga_id"), event["event"], json.dumps(event), status,
                   datetime.now(timezone.utc).isoformat()))


def mark_duplicate(message_id) -> None:
    with sqlite3.connect(settings.db_path) as c:
        c.execute("UPDATE inbox SET deliveries = deliveries + 1 WHERE message_id=?", (message_id,))


def list_messages(user_id: str | None) -> list[dict]:
    with sqlite3.connect(settings.db_path) as c:
        rows = c.execute("SELECT message_id,saga_id,event,status,deliveries,received_at FROM inbox "
                         "WHERE ?1 IS NULL OR payload LIKE '%\"user_id\": \"' || ?1 || '\"%' "
                         "ORDER BY received_at DESC LIMIT 50", (user_id,)).fetchall()
    keys = ["message_id", "saga_id", "event", "status", "deliveries", "received_at"]
    return [dict(zip(keys, r)) for r in rows]
