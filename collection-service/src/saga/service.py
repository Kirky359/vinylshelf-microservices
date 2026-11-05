"""SAGA 'complete album': state transitions and compensation (the background workers live in coordinator.py)."""
import uuid

from src import database as db
from src.collection.constants import Status
from src.collection.repository import CollectionRepository
from src.outbox.service import OutboxService
from src.saga import exceptions
from src.saga.constants import FINAL_STATES, State
from src.saga.repository import SagaRepository


class SagaService:
    def __init__(self, outbox: OutboxService):
        self.outbox = outbox

    def start_saga(self, conn, user_id: str, album_id: str, prev_status: str) -> str:
        """Local transaction #1 of the saga: status -> CompletionPending + saga_log (+ outbox event, added by the caller)."""
        saga_id = str(uuid.uuid4())
        SagaRepository(conn).create(saga_id, user_id, album_id, prev_status)
        CollectionRepository(conn).set_status(user_id, album_id, Status.COMPLETION_PENDING)
        return saga_id

    def confirm(self, saga_id: str) -> str:
        """Consumer confirmed processing: finish the saga. Idempotent. Returns resulting state."""
        with db.tx() as conn:
            sagas = SagaRepository(conn)
            saga = sagas.get(saga_id)
            if saga["state"] in FINAL_STATES:
                return saga["state"]
            CollectionRepository(conn).set_status(
                saga["user_id"], saga["album_id"], Status.COMPLETED, only_if=Status.COMPLETION_PENDING)
            sagas.set_state(saga_id, State.PROCESSED)
        print(f"[saga] {saga_id} confirmed by consumer -> processed", flush=True)
        return State.PROCESSED

    def compensate(self, saga_id: str, reason: str) -> str:
        """Compensating transaction: undo the status change. Idempotent. Returns resulting state."""
        with db.tx() as conn:
            sagas = SagaRepository(conn)
            saga = sagas.get(saga_id)
            if saga["state"] in FINAL_STATES:
                return saga["state"]
            CollectionRepository(conn).set_status(
                saga["user_id"], saga["album_id"], saga["prev_status"], only_if=Status.COMPLETION_PENDING)
            sagas.set_state(saga_id, State.COMPENSATED, reason)
            self.outbox.add_event(conn, "collection.album_completion_cancelled",
                                  {"user_id": saga["user_id"], "album_id": saga["album_id"], "reason": reason}, saga_id)
        print(f"[saga] {saga_id} compensated, status restored to {saga['prev_status']}: {reason}", flush=True)
        return State.COMPENSATED

    def find_pending(self, user_id: str, album_id: str) -> str:
        with db.tx() as conn:
            saga_id = SagaRepository(conn).find_pending_id(user_id, album_id)
        if saga_id is None:
            raise exceptions.NoPendingSaga()
        return saga_id

    def read_saga(self, saga_id: str) -> dict:
        with db.tx() as conn:
            return dict(SagaRepository(conn).get(saga_id))

    def list_sagas(self, user_id: str | None) -> list[dict]:
        with db.tx() as conn:
            return SagaRepository(conn).list_by_user(user_id)
