import sqlite3

from fastapi.concurrency import run_in_threadpool

from src import database as db
from src.collection import exceptions
from src.collection.constants import LOCKED_STATUSES, Status
from src.collection.schemas import AddAlbum
from src.discovery import call
from src.outbox import service as outbox_service
from src.saga import service as saga_service


def get_item(conn, user_id: str, album_id: str) -> dict:
    row = conn.execute("SELECT * FROM collection_items WHERE user_id=? AND album_id=?", (user_id, album_id)).fetchone()
    if not row:
        raise exceptions.ItemNotFound()
    return dict(row)


def read_item(user_id: str, album_id: str) -> dict:
    with db.tx() as conn:
        return get_item(conn, user_id, album_id)


def list_items(user_id: str) -> list[dict]:
    with db.tx() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM collection_items WHERE user_id=?", (user_id,)).fetchall()]


def _assert_not_in_collection(body: AddAlbum) -> None:
    with db.tx() as conn:
        if conn.execute("SELECT 1 FROM collection_items WHERE user_id=? AND album_id=?",
                        (body.user_id, body.album_id)).fetchone():
            raise exceptions.AlreadyInCollection()  # invariant


def _insert_item(user_id: str, item: dict) -> None:
    with db.tx() as conn:  # data + outbox event in ONE local transaction
        try:
            conn.execute(
                "INSERT INTO collection_items (user_id,album_id,title,artist,genre,tracks_total,tracks_played,status) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (user_id, item["album_id"], item["title"], item["artist"], item["genre"],
                 item["tracks_total"], 0, Status.PLANNED))
        except sqlite3.IntegrityError:
            raise exceptions.AlreadyInCollection()
        outbox_service.add_event(conn, "collection.album_added", {"user_id": user_id, **item})


async def add_album(body: AddAlbum) -> tuple[dict, dict]:
    """Returns (item, catalog album)."""
    await run_in_threadpool(_assert_not_in_collection, body)
    # synchronous call: collection-service -> catalog-service (found via Consul)
    r = await call("catalog-service", "GET", f"/catalog/albums/{body.album_id}")
    if r.status_code != 200:
        raise exceptions.AlbumNotInCatalog(r.status_code)
    album = r.json()
    item = {
        "album_id": album["id"], "title": album["title"], "artist": album["artist"], "genre": album["genre"],
        "tracks_total": album["tracks"], "tracks_played": 0, "status": Status.PLANNED,
    }
    await run_in_threadpool(_insert_item, body.user_id, item)
    return item, album


def update_progress(user_id: str, album_id: str, tracks_played: int) -> dict:
    with db.tx() as conn:
        item = get_item(conn, user_id, album_id)
        if item["status"] in LOCKED_STATUSES:
            raise exceptions.ItemLocked(item["status"])
        if not 0 <= tracks_played <= item["tracks_total"]:
            raise exceptions.TracksOutOfRange()
        delta = tracks_played - item["tracks_played"]
        item["tracks_played"] = tracks_played
        if tracks_played > 0:
            item["status"] = Status.LISTENING
        conn.execute("UPDATE collection_items SET tracks_played=?, status=? WHERE user_id=? AND album_id=?",
                     (item["tracks_played"], item["status"], user_id, album_id))
        outbox_service.add_event(conn, "collection.progress_updated",
                                 {"user_id": user_id, "album_id": album_id, "tracks_delta": delta,
                                  "genre": item["genre"], "artist": item["artist"]})
    return item


def complete(user_id: str, album_id: str) -> dict:
    """Starts the SAGA: the album becomes CompletionPending until analytics-consumer confirms."""
    with db.tx() as conn:
        item = get_item(conn, user_id, album_id)
        if item["status"] in LOCKED_STATUSES:
            raise exceptions.ItemLocked(item["status"], already=True)
        if item["tracks_played"] < item["tracks_total"]:  # invariant
            raise exceptions.NotAllTracksPlayed()
        saga_id = saga_service.start_saga(conn, user_id, album_id, item["status"])
        outbox_service.add_event(conn, "collection.album_completed",
                                 {"user_id": user_id, "album_id": album_id, "genre": item["genre"],
                                  "artist": item["artist"], "tracks": item["tracks_total"]}, saga_id)
    return {**item, "status": Status.COMPLETION_PENDING, "saga_id": saga_id}
