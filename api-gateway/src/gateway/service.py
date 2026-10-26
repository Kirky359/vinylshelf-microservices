from fastapi import Request, Response

from src.discovery import call
from src.gateway import constants, exceptions


async def forward(service: str, path: str, request: Request) -> Response:
    if service not in constants.ROUTES:
        raise exceptions.UnknownService(service)
    try:
        r = await call(service, request.method, "/" + path, params=dict(request.query_params),
                       content=await request.body(),
                       headers={"content-type": request.headers.get("content-type", "application/json")})
    except LookupError as exc:
        raise exceptions.ServiceUnavailable(str(exc))
    except ConnectionError as exc:
        raise exceptions.BadGateway(str(exc))
    return Response(r.content, r.status_code, media_type=r.headers.get("content-type"))
