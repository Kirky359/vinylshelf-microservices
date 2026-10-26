from fastapi import HTTPException


class SagaNotFound(HTTPException):
    def __init__(self):
        super().__init__(404, "unknown saga")


class NoPendingSaga(HTTPException):
    def __init__(self):
        super().__init__(404, "no pending saga for this album")
