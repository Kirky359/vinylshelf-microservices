from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.catalog.router import router as catalog_router
from src.config import settings
from src.discovery import deregister, register
from src.system.router import router as system_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    instance_id = await register(settings.service_name, settings.service_port)
    yield
    await deregister(instance_id)


app = FastAPI(title="Catalog Service (Search & Metadata)", lifespan=lifespan)
app.include_router(system_router)
app.include_router(catalog_router)
