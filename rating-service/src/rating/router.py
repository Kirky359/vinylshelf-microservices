from fastapi import APIRouter

from src.discovery import HOSTNAME
from src.rating import service
from src.rating.schemas import Rate, RatingCreated, UserRatings

router = APIRouter(prefix="/rating", tags=["rating"])


@router.post("/rate", status_code=201, response_model=RatingCreated)
async def rate(body: Rate):
    await service.rate(body)
    return {"user_id": body.user_id, "album_id": body.album_id, "rating": body.rating, "served_by": HOSTNAME}


@router.get("/{user_id}", response_model=UserRatings)
def list_ratings(user_id: str):
    return {"ratings": service.list_ratings(user_id)}
