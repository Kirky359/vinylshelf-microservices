from fastapi import HTTPException


class Unauthorized(HTTPException):
    def __init__(self, detail: str):
        super().__init__(401, detail,
                         headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{detail}"'})


class MissingToken(HTTPException):
    def __init__(self):
        super().__init__(401, "missing bearer token", headers={"WWW-Authenticate": "Bearer"})


class InsufficientScope(HTTPException):
    def __init__(self, scope: str):
        super().__init__(403, f"insufficient scope, required: {scope}",
                         headers={"WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{scope}"'})


class AuthServerUnavailable(HTTPException):
    def __init__(self):
        super().__init__(503, "authorization server is unavailable")
