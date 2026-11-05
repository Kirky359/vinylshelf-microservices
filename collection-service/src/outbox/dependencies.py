from functools import lru_cache

from src.outbox.service import OutboxDispatcher, OutboxService


@lru_cache
def get_outbox_service() -> OutboxService:
    return OutboxService()


@lru_cache
def get_outbox_dispatcher() -> OutboxDispatcher:
    return OutboxDispatcher()
