from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.discovery import deregister, register
from src.gateway.router import router as gateway_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    instance_id = await register(settings.service_name, settings.service_port)
    yield
    await deregister(instance_id)


app = FastAPI(title="VinylShelf API Gateway (edge service)", lifespan=lifespan)
app.include_router(gateway_router)
