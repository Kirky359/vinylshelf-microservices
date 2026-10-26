from fastapi import APIRouter, Request

from src.config import settings
from src.discovery import chain, instances
from src.gateway import constants, service

router = APIRouter()


@router.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@router.get("/discovery/{service_name}", tags=["system"])
async def discovery(service_name: str):
    """What Consul currently knows about a service (healthy instances only)."""
    return {"service": service_name, "instances": await instances(service_name)}


@router.get("/chain", tags=["system"])
async def chain_endpoint(text: str = "hello", route: str = constants.DEFAULT_CHAIN):
    """Synchronous chain: every service appends its name and forwards the request further."""
    return await chain(settings.service_name, text, route)


# catch-all proxy: must be registered after every other route
@router.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], tags=["proxy"])
async def proxy(service_name: str, path: str, request: Request):
    return await service.forward(service_name, path, request)
