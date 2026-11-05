from fastapi import APIRouter, Depends

from src.saga.dependencies import get_saga_service
from src.saga.schemas import RollbackRequest, SagaRef
from src.saga.service import SagaService

router = APIRouter(tags=["saga"])


@router.post("/saga/confirm")
def saga_confirm(body: SagaRef, service: SagaService = Depends(get_saga_service)):
    return {"saga_id": body.saga_id, "state": service.confirm(body.saga_id)}


@router.post("/collection/rollback")
def rollback(body: RollbackRequest, service: SagaService = Depends(get_saga_service)):
    """Manual compensation of the latest pending saga of an album (the coordinator uses the same method)."""
    saga_id = service.find_pending(body.user_id, body.album_id)
    return {"saga_id": saga_id, "state": service.compensate(saga_id, "manual rollback")}


@router.get("/saga/{saga_id}")
def get_saga(saga_id: str, service: SagaService = Depends(get_saga_service)):
    return service.read_saga(saga_id)


@router.get("/saga")
def list_sagas(user_id: str | None = None, service: SagaService = Depends(get_saga_service)):
    return {"sagas": service.list_sagas(user_id)}
