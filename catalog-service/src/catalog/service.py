from src.catalog import exceptions
from src.catalog.models import ALBUMS


def search(q: str) -> list[dict]:
    q = q.lower()
    return [a for a in ALBUMS.values() if q in a["title"].lower() or q in a["artist"].lower() or q in a["genre"].lower()]


def get_album(album_id: str) -> dict:
    if album_id not in ALBUMS:
        raise exceptions.AlbumNotFound()
    return ALBUMS[album_id]
