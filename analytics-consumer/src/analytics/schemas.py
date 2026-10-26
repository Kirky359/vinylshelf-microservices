from pydantic import BaseModel


class Dashboard(BaseModel):
    user_id: str
    albums_completed: int
    tracks_played: int
    average_rating: float | None
    top_genres: list[tuple[str, int]]
    top_artists: list[tuple[str, int]]
    served_by: str
