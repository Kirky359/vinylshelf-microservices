from pydantic import BaseModel, Field


class Rate(BaseModel):
    user_id: str
    album_id: str
    rating: int = Field(ge=1, le=10)


class RatingCreated(BaseModel):
    user_id: str
    album_id: str
    rating: int
    served_by: str


class UserRatings(BaseModel):
    ratings: dict[str, int]
