from fastapi import APIRouter, Depends

from src.collection import service
from src.collection.dependencies import valid_item
from src.collection.schemas import AddAlbum, Progress
from src.discovery import HOSTNAME

router = APIRouter(prefix="/collection", tags=["collection"])


@router.post("/add", status_code=201)
async def add_album(body: AddAlbum):
    item, album = await service.add_album(body)
    return {**item, "metadata_from": album["served_by"], "served_by": HOSTNAME}


@router.post("/{user_id}/{album_id}/progress")
def update_progress(user_id: str, album_id: str, body: Progress):
    return service.update_progress(user_id, album_id, body.tracks_played)


@router.post("/{user_id}/{album_id}/complete", status_code=202)
def complete(user_id: str, album_id: str):
    return service.complete(user_id, album_id)


@router.get("/{user_id}/{album_id}")
def get_item(item: dict = Depends(valid_item)):
    return item


@router.get("/{user_id}")
def get_collection(user_id: str):
    return {"items": service.list_items(user_id), "served_by": HOSTNAME}
