from contextlib import asynccontextmanager

from fastapi import FastAPI

from src import database
from src.collection.router import router as collection_router
from src.config import settings
from src.discovery import deregister, register
from src.models import SCHEMA
from src.outbox import service as outbox_service
from src.outbox.router import router as outbox_router
from src.saga import service as saga_service
from src.saga.router import router as saga_router
from src.system.router import router as system_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init(SCHEMA)
    outbox_service.start()
    saga_service.start()
    instance_id = await register(settings.service_name, settings.service_port)
    yield
    outbox_service.stop()
    saga_service.stop()
    await deregister(instance_id)


app = FastAPI(title="Collection Service (Collection Management)", lifespan=lifespan)
app.include_router(system_router)
# the saga router holds /collection/rollback, so it goes before the parametrised /collection/{user_id}/... routes
app.include_router(saga_router)
app.include_router(collection_router)
app.include_router(outbox_router)
