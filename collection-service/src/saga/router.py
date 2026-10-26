from fastapi import APIRouter

from src.saga import service
from src.saga.schemas import RollbackRequest, SagaRef

router = APIRouter(tags=["saga"])


@router.post("/saga/confirm")
def saga_confirm(body: SagaRef):
    return {"saga_id": body.saga_id, "state": service.confirm(body.saga_id)}


@router.post("/collection/rollback")
def rollback(body: RollbackRequest):
    """Manual compensation of the latest pending saga of an album (the coordinator uses the same function)."""
    saga_id = service.find_pending(body.user_id, body.album_id)
    return {"saga_id": saga_id, "state": service.compensate(saga_id, "manual rollback")}


@router.get("/saga/{saga_id}")
def get_saga(saga_id: str):
    return service.read_saga(saga_id)


@router.get("/saga")
def list_sagas(user_id: str | None = None):
    return {"sagas": service.list_sagas(user_id)}
