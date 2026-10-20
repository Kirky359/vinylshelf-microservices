import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response

from app.discovery import HOSTNAME, call, chain, instances, deregister, register

NAME, PORT = "api-gateway", 8080


@asynccontextmanager
async def lifespan(app):
    instance_id = await register(NAME, PORT)
    yield
    await deregister(instance_id)


app = FastAPI(title="VinylShelf API Gateway (edge service)", lifespan=lifespan)

ROUTES = {"auth-service", "catalog-service", "collection-service", "rating-service", "analytics-service"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/discovery/{service}")
async def discovery(service: str):
    """What Consul currently knows about a service (healthy instances only)."""
    return {"service": service, "instances": await instances(service)}


@app.get("/chain")
async def chain_endpoint(text: str = "hello", route: str = "auth-service,collection-service,catalog-service"):
    """Synchronous chain: every service appends its name and forwards the request further."""
    return await chain(NAME, text, route)


@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(service: str, path: str, request: Request):
    if service not in ROUTES:
        raise HTTPException(404, f"unknown service {service}")
    try:
        r = await call(service, request.method, "/" + path, params=dict(request.query_params),
                       content=await request.body(), headers={"content-type": request.headers.get("content-type", "application/json")})
    except LookupError as exc:
        raise HTTPException(503, str(exc))
    except ConnectionError as exc:
        raise HTTPException(502, str(exc))
    return Response(r.content, r.status_code, media_type=r.headers.get("content-type"))
