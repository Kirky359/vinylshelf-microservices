from functools import lru_cache

from fastapi import Depends

from src.collection.client import CatalogClient
from src.collection.service import CollectionService
from src.outbox.dependencies import get_outbox_service
from src.saga.dependencies import get_saga_service


@lru_cache
def get_collection_service() -> CollectionService:
    return CollectionService(get_outbox_service(), get_saga_service(), CatalogClient())


def valid_item(user_id: str, album_id: str, service: CollectionService = Depends(get_collection_service)) -> dict:
    return service.read_item(user_id, album_id)
