from src.collection import exceptions
from src.discovery import call


class CatalogClient:
    """Synchronous call collection-service -> catalog-service (found via Consul)."""

    service_name = "catalog-service"

    async def get_album(self, album_id: str) -> dict:
        r = await call(self.service_name, "GET", f"/catalog/albums/{album_id}")
        if r.status_code != 200:
            raise exceptions.AlbumNotInCatalog(r.status_code)
        return r.json()
