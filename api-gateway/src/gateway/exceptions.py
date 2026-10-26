from fastapi import HTTPException


class UnknownService(HTTPException):
    def __init__(self, service: str):
        super().__init__(404, f"unknown service {service}")


class ServiceUnavailable(HTTPException):
    def __init__(self, detail: str):
        super().__init__(503, detail)


class BadGateway(HTTPException):
    def __init__(self, detail: str):
        super().__init__(502, detail)
