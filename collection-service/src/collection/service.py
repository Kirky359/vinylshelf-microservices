from fastapi.concurrency import run_in_threadpool

from src import database as db
from src.collection import exceptions
from src.collection.client import CatalogClient
from src.collection.constants import LOCKED_STATUSES, Status
from src.collection.repository import CollectionRepository
from src.collection.schemas import AddAlbum
from src.outbox.service import OutboxService
from src.saga.service import SagaService


class CollectionService:
    def __init__(self, outbox: OutboxService, saga: SagaService, catalog: CatalogClient):
        self.outbox = outbox
        self.saga = saga
        self.catalog = catalog

    def read_item(self, user_id: str, album_id: str) -> dict:
        with db.tx() as conn:
            return CollectionRepository(conn).get(user_id, album_id)

    def list_items(self, user_id: str) -> list[dict]:
        with db.tx() as conn:
            return CollectionRepository(conn).list_by_user(user_id)

    async def add_album(self, body: AddAlbum) -> tuple[dict, dict]:
        """Returns (item, catalog album)."""
        await run_in_threadpool(self._assert_not_in_collection, body)
        album = await self.catalog.get_album(body.album_id)
        item = {
            "album_id": album["id"], "title": album["title"], "artist": album["artist"], "genre": album["genre"],
            "tracks_total": album["tracks"], "tracks_played": 0, "status": Status.PLANNED,
        }
        await run_in_threadpool(self._insert_item, body.user_id, item)
        return item, album

    def update_progress(self, user_id: str, album_id: str, tracks_played: int) -> dict:
        with db.tx() as conn:
            repo = CollectionRepository(conn)
            item = repo.get(user_id, album_id)
            if item["status"] in LOCKED_STATUSES:
                raise exceptions.ItemLocked(item["status"])
            if not 0 <= tracks_played <= item["tracks_total"]:
                raise exceptions.TracksOutOfRange()
            delta = tracks_played - item["tracks_played"]
            item["tracks_played"] = tracks_played
            if tracks_played > 0:
                item["status"] = Status.LISTENING
            repo.update_progress(user_id, album_id, item["tracks_played"], item["status"])
            self.outbox.add_event(conn, "collection.progress_updated",
                                  {"user_id": user_id, "album_id": album_id, "tracks_delta": delta,
                                   "genre": item["genre"], "artist": item["artist"]})
        return item

    def complete(self, user_id: str, album_id: str) -> dict:
        """Starts the SAGA: the album becomes CompletionPending until analytics-consumer confirms."""
        with db.tx() as conn:
            item = CollectionRepository(conn).get(user_id, album_id)
            if item["status"] in LOCKED_STATUSES:
                raise exceptions.ItemLocked(item["status"], already=True)
            if item["tracks_played"] < item["tracks_total"]:  # invariant
                raise exceptions.NotAllTracksPlayed()
            saga_id = self.saga.start_saga(conn, user_id, album_id, item["status"])
            self.outbox.add_event(conn, "collection.album_completed",
                                  {"user_id": user_id, "album_id": album_id, "genre": item["genre"],
                                   "artist": item["artist"], "tracks": item["tracks_total"]}, saga_id)
        return {**item, "status": Status.COMPLETION_PENDING, "saga_id": saga_id}

    def _assert_not_in_collection(self, body: AddAlbum) -> None:
        with db.tx() as conn:
            if CollectionRepository(conn).exists(body.user_id, body.album_id):
                raise exceptions.AlreadyInCollection()  # invariant

    def _insert_item(self, user_id: str, item: dict) -> None:
        with db.tx() as conn:  # data + outbox event in ONE local transaction
            CollectionRepository(conn).insert(user_id, item)
            self.outbox.add_event(conn, "collection.album_added", {"user_id": user_id, **item})
