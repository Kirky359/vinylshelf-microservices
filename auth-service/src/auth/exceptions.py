from fastapi import HTTPException


class UsernameTaken(HTTPException):
    def __init__(self):
        super().__init__(409, "username taken")


class BadCredentials(HTTPException):
    def __init__(self):
        super().__init__(401, "bad credentials")
