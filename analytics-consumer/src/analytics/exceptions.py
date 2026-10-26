from fastapi import HTTPException


class NoStatistics(HTTPException):
    def __init__(self):
        super().__init__(404, "no statistics for this user yet (or they live on another consumer instance)")
