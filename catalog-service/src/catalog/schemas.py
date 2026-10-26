from pydantic import BaseModel


class Album(BaseModel):
    id: str
    title: str
    artist: str
    genre: str
    tracks: int
    served_by: str


class SearchResult(BaseModel):
    items: list[dict]
    served_by: str
