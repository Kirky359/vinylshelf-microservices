from fastapi import HTTPException


class AlbumNotFound(HTTPException):
    def __init__(self):
        super().__init__(404, "album not found")
