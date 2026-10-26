from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.auth.router import router as auth_router
from src.config import settings
from src.discovery import deregister, register
from src.system.router import router as system_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    instance_id = await register(settings.service_name, settings.service_port)
    yield
    await deregister(instance_id)


app = FastAPI(title="Auth Service (User Management)", lifespan=lifespan)
app.include_router(system_router)
app.include_router(auth_router)
