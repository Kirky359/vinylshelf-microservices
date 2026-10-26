from fastapi import APIRouter

from src.discovery import HOSTNAME
from src.inbox import service

router = APIRouter(prefix="/analytics", tags=["inbox"])


@router.get("/inbox")
def inbox_view(user_id: str | None = None):
    return {"handled_by": HOSTNAME, "inbox": service.list_messages(user_id)}
