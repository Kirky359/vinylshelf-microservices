import sqlite3

from src.collection import exceptions
from src.collection.constants import Status


class CollectionRepository:
    """SQL for collection_items. Works inside the caller's transaction (the connection is passed in)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, user_id: str, album_id: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM collection_items WHERE user_id=? AND album_id=?", (user_id, album_id)).fetchone()
        if not row:
            raise exceptions.ItemNotFound()
        return dict(row)

    def list_by_user(self, user_id: str) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM collection_items WHERE user_id=?", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def exists(self, user_id: str, album_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM collection_items WHERE user_id=? AND album_id=?", (user_id, album_id)).fetchone() is not None

    def insert(self, user_id: str, item: dict) -> None:
        try:
            self.conn.execute(
                "INSERT INTO collection_items (user_id,album_id,title,artist,genre,tracks_total,tracks_played,status) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (user_id, item["album_id"], item["title"], item["artist"], item["genre"],
                 item["tracks_total"], 0, Status.PLANNED))
        except sqlite3.IntegrityError:
            raise exceptions.AlreadyInCollection()

    def update_progress(self, user_id: str, album_id: str, tracks_played: int, status: str) -> None:
        self.conn.execute("UPDATE collection_items SET tracks_played=?, status=? WHERE user_id=? AND album_id=?",
                          (tracks_played, status, user_id, album_id))

    def set_status(self, user_id: str, album_id: str, status: str, only_if: str | None = None) -> None:
        """Change the status; with only_if the update is applied only when the current status matches."""
        sql = "UPDATE collection_items SET status=? WHERE user_id=? AND album_id=?"
        params = [status, user_id, album_id]
        if only_if is not None:
            sql += " AND status=?"
            params.append(only_if)
        self.conn.execute(sql, params)
