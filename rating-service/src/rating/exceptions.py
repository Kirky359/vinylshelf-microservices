from fastapi import HTTPException


class NotInCollection(HTTPException):
    def __init__(self):
        super().__init__(404, "album is not in the user's collection")


class NotRatable(HTTPException):
    def __init__(self):
        super().__init__(409, "album can be rated only when listening or completed")
