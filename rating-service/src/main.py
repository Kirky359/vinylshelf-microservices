from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.rating.router import router as rating_router
from src.config import settings
from src.discovery import deregister, register
from src.system.router import router as system_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    instance_id = await register(settings.service_name, settings.service_port)
    yield
    await deregister(instance_id)


app = FastAPI(title="Rating Service (Rating Management)", lifespan=lifespan)
app.include_router(system_router)
app.include_router(rating_router)
