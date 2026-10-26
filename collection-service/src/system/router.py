from fastapi import APIRouter

from src.config import settings
from src.discovery import chain

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/chain")
async def chain_endpoint(text: str, route: str = ""):
    return await chain(settings.service_name, text, route)
