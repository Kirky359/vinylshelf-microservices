from fastapi import APIRouter

from src.analytics import models, service
from src.analytics.schemas import Dashboard
from src.discovery import HOSTNAME

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/events/log")
def events_log():
    return {"handled_by": HOSTNAME, "events": list(models.LOG)}


@router.get("/{user_id}/dashboard", response_model=Dashboard)
def dashboard(user_id: str):
    return service.dashboard(user_id)
