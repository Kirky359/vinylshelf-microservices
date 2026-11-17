from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.discovery import deregister, register
from src.gateway.router import router as gateway_router
from src.security.config import security_settings
from src.security.constants import SCOPES
from src.security.router import router as security_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    instance_id = await register(settings.service_name, settings.service_port)
    yield
    await deregister(instance_id)


app = FastAPI(
    title="VinylShelf API Gateway (edge service)", lifespan=lifespan,
    swagger_ui_init_oauth={"clientId": security_settings.swagger_client_id, "usePkceWithAuthorizationCodeGrant": True,
                           "scopes": "openid " + " ".join(SCOPES)},
)
# CORS is answered by the gateway only: the proxy forwards no CORS headers from the services and adds
# nothing that could overwrite them, so the browser gets exactly one set of Access-Control-* headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,  # the bearer token is sent in a header, not in cookies
    max_age=600,
)
app.include_router(security_router)
app.include_router(gateway_router)  # catch-all proxy: must be the last one
