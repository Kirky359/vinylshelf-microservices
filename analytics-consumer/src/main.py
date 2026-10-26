import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.analytics import consumer
from src.analytics.router import router as analytics_router
from src.config import settings
from src.discovery import deregister, register
from src.inbox import service as inbox_service
from src.inbox.router import router as inbox_router
from src.system.router import router as system_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    consumer.set_loop(asyncio.get_running_loop())
    inbox_service.init()
    instance_id = await register(settings.service_name, settings.service_port)
    consumer.start()
    yield
    consumer.stop()
    await deregister(instance_id)


app = FastAPI(title="Analytics Service (consumer + dashboard)", lifespan=lifespan)
app.include_router(system_router)
app.include_router(inbox_router)
app.include_router(analytics_router)
