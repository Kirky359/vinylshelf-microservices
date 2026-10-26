from fastapi import HTTPException


class ItemNotFound(HTTPException):
    def __init__(self):
        super().__init__(404, "album is not in the collection")


class AlreadyInCollection(HTTPException):
    def __init__(self):
        super().__init__(409, "album already in collection")


class AlbumNotInCatalog(HTTPException):
    def __init__(self, status_code: int):
        super().__init__(status_code, "album not found in catalog")


class ItemLocked(HTTPException):
    def __init__(self, status: str, already: bool = False):
        super().__init__(409, f"album is {'already ' if already else ''}{status}")


class TracksOutOfRange(HTTPException):
    def __init__(self):
        super().__init__(422, "tracks_played out of range")


class NotAllTracksPlayed(HTTPException):
    def __init__(self):
        super().__init__(409, "not all tracks are played yet")
