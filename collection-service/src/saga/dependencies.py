from functools import lru_cache

from src.outbox.dependencies import get_outbox_service
from src.saga.config import saga_settings
from src.saga.coordinator import SagaCoordinator
from src.saga.service import SagaService


@lru_cache
def get_saga_service() -> SagaService:
    return SagaService(get_outbox_service())


@lru_cache
def get_saga_coordinator() -> SagaCoordinator:
    return SagaCoordinator(get_saga_service(), saga_settings)
