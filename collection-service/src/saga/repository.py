import sqlite3

from src.saga import exceptions
from src.saga.constants import State
from src.utils import now


class SagaRepository:
    """SQL for saga_log. Works inside the caller's transaction (the connection is passed in)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, saga_id: str, user_id: str, album_id: str, prev_status: str) -> None:
        self.conn.execute(
            "INSERT INTO saga_log (saga_id,user_id,album_id,prev_status,state,started_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (saga_id, user_id, album_id, prev_status, State.STARTED, now(), now()),
        )

    def get(self, saga_id: str) -> sqlite3.Row:
        saga = self.conn.execute("SELECT * FROM saga_log WHERE saga_id=?", (saga_id,)).fetchone()
        if saga is None:
            raise exceptions.SagaNotFound()
        return saga

    def set_state(self, saga_id: str, state: str, reason: str | None = None) -> None:
        if reason is None:
            self.conn.execute("UPDATE saga_log SET state=?, updated_at=? WHERE saga_id=?", (state, now(), saga_id))
        else:
            self.conn.execute("UPDATE saga_log SET state=?, reason=?, updated_at=? WHERE saga_id=?",
                              (state, reason, now(), saga_id))

    def find_pending_id(self, user_id: str, album_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT saga_id FROM saga_log WHERE user_id=? AND album_id=? AND state IN ('started','sent') "
            "ORDER BY started_at DESC LIMIT 1", (user_id, album_id)).fetchone()
        return row["saga_id"] if row else None

    def list_by_user(self, user_id: str | None) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM saga_log WHERE ?1 IS NULL OR user_id=?1 ORDER BY started_at DESC LIMIT 50", (user_id,))
        return [dict(r) for r in rows]

    def list_unfinished(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT saga_id, updated_at FROM saga_log WHERE state IN ('started','sent')").fetchall()

    def list_with_failed_outbox_ids(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT o.saga_id FROM outbox o JOIN saga_log s ON s.saga_id=o.saga_id "
            "WHERE o.status='failed' AND o.event_type='collection.album_completed' AND s.state IN ('started','sent')")
        return [r["saga_id"] for r in rows]
