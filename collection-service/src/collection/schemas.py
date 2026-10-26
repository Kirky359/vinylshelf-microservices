from pydantic import BaseModel


class AddAlbum(BaseModel):
    user_id: str
    album_id: str


class Progress(BaseModel):
    tracks_played: int
