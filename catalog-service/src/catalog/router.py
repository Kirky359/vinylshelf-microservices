from fastapi import APIRouter, Depends

from src.catalog import service
from src.catalog.dependencies import valid_album
from src.catalog.schemas import Album, SearchResult
from src.discovery import HOSTNAME

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/search", response_model=SearchResult)
def search(q: str = ""):
    return {"items": service.search(q), "served_by": HOSTNAME}


@router.get("/albums/{album_id}", response_model=Album)
def get_album(album: dict = Depends(valid_album)):
    return {**album, "served_by": HOSTNAME}
