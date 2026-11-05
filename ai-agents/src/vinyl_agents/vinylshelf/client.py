from typing import Any
from urllib.parse import quote

import httpx

from vinyl_agents.config import Settings
from vinyl_agents.exceptions import ApiError


class VinylShelfClient:
    """REST client of the lab 3 system. Everything goes through the api-gateway (routing + Consul discovery)."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(base_url=settings.gateway_url, timeout=settings.http_timeout_seconds,
                                       transport=transport)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(503, f"gateway is unreachable: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(response.status_code, str(detail))
        return response.json()

    @staticmethod
    def _seg(value: str) -> str:
        return quote(value, safe="")  # a path segment can never contain "/" or ".."

    # auth-service
    async def register(self, username: str, password: str) -> dict:
        return await self._request("POST", "/auth-service/auth/register",
                                   json={"username": username, "password": password})

    async def login(self, username: str, password: str) -> dict:
        return await self._request("POST", "/auth-service/auth/login",
                                   json={"username": username, "password": password})

    # catalog-service
    async def search_albums(self, q: str) -> dict:
        return await self._request("GET", "/catalog-service/catalog/search", params={"q": q})

    async def get_album(self, album_id: str) -> dict:
        return await self._request("GET", f"/catalog-service/catalog/albums/{self._seg(album_id)}")

    # collection-service
    async def get_collection(self, user_id: str) -> dict:
        return await self._request("GET", f"/collection-service/collection/{self._seg(user_id)}")

    async def add_album(self, user_id: str, album_id: str) -> dict:
        return await self._request("POST", "/collection-service/collection/add",
                                   json={"user_id": user_id, "album_id": album_id})

    async def update_progress(self, user_id: str, album_id: str, tracks_played: int) -> dict:
        return await self._request(
            "POST", f"/collection-service/collection/{self._seg(user_id)}/{self._seg(album_id)}/progress",
            json={"tracks_played": tracks_played})

    async def complete_album(self, user_id: str, album_id: str) -> dict:
        return await self._request(
            "POST", f"/collection-service/collection/{self._seg(user_id)}/{self._seg(album_id)}/complete")

    async def get_saga(self, saga_id: str) -> dict:
        return await self._request("GET", f"/collection-service/saga/{self._seg(saga_id)}")

    # rating-service
    async def rate_album(self, user_id: str, album_id: str, rating: int) -> dict:
        return await self._request("POST", "/rating-service/rating/rate",
                                   json={"user_id": user_id, "album_id": album_id, "rating": rating})

    # analytics-consumer
    async def get_dashboard(self, user_id: str) -> dict:
        return await self._request("GET", f"/analytics-service/analytics/{self._seg(user_id)}/dashboard")

    async def get_inbox(self, user_id: str | None = None) -> dict:
        return await self._request("GET", "/analytics-service/analytics/inbox",
                                   params={"user_id": user_id} if user_id else None)
