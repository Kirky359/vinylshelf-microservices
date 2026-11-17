from fastapi import Request, Response

from src.discovery import call
from src.gateway import constants, exceptions
from src.security.schemas import Principal


async def forward(service: str, path: str, request: Request, principal: Principal | None = None) -> Response:
    if service not in constants.ROUTES:
        raise exceptions.UnknownService(service)
    # the headers are built from scratch: nothing the client sent (X-User-Id included) reaches the services
    headers = {"content-type": request.headers.get("content-type", "application/json")}
    if principal:
        headers["x-user-id"] = principal.subject
        headers["x-user-scopes"] = " ".join(sorted(principal.scopes))
    try:
        r = await call(service, request.method, "/" + path, params=dict(request.query_params),
                       content=await request.body(), headers=headers)
    except LookupError as exc:
        raise exceptions.ServiceUnavailable(str(exc))
    except ConnectionError as exc:
        raise exceptions.BadGateway(str(exc))
    return Response(r.content, r.status_code, media_type=r.headers.get("content-type"))
