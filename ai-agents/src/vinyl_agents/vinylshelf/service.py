import asyncio
import time

from vinyl_agents.config import Settings
from vinyl_agents.exceptions import ApiError
from vinyl_agents.vinylshelf.client import VinylShelfClient

FINAL_SAGA_STATES = ("processed", "compensated")


class VinylShelfService:
    """Use cases of the VinylShelf domain. LLM tools, MCP tools and A2A skills all call this class, never the client."""

    def __init__(self, client: VinylShelfClient, settings: Settings):
        self._client = client
        self._saga_wait = settings.saga_wait_seconds

    async def search_catalog(self, q: str) -> dict:
        return await self._client.search_albums(q)

    async def get_album(self, album_id: str) -> dict:
        return await self._client.get_album(album_id)

    async def get_collection(self, user_id: str) -> dict:
        return await self._client.get_collection(user_id)

    async def add_album(self, user_id: str, album_id: str) -> dict:
        return await self._client.add_album(user_id, album_id)

    async def update_progress(self, user_id: str, album_id: str, tracks_played: int) -> dict:
        return await self._client.update_progress(user_id, album_id, tracks_played)

    async def complete_album(self, user_id: str, album_id: str, wait: bool = True) -> dict:
        """Starts the completion SAGA (HTTP 202). With wait=True blocks until it is processed or compensated."""
        started = await self._client.complete_album(user_id, album_id)
        saga_id = started["saga_id"]
        if not wait:
            return {"album_id": album_id, "saga_id": saga_id, "saga_state": "started",
                    "album_status": started["status"]}
        saga = await self.wait_for_saga(saga_id)
        item = await self._client.get_collection(user_id)
        status = next((i["status"] for i in item["items"] if i["album_id"] == album_id), None)
        return {"album_id": album_id, "saga_id": saga_id, "saga_state": saga["state"],
                "reason": saga.get("reason"), "album_status": status}

    async def get_saga(self, saga_id: str) -> dict:
        return await self._client.get_saga(saga_id)

    async def wait_for_saga(self, saga_id: str) -> dict:
        deadline = time.monotonic() + self._saga_wait
        while True:
            saga = await self._client.get_saga(saga_id)
            if saga["state"] in FINAL_SAGA_STATES or time.monotonic() >= deadline:
                return saga
            await asyncio.sleep(1)

    async def rate_album(self, user_id: str, album_id: str, rating: int) -> dict:
        return await self._client.rate_album(user_id, album_id, rating)

    async def get_dashboard(self, user_id: str) -> dict:
        try:
            return await self._client.get_dashboard(user_id)
        except ApiError as exc:
            if exc.status_code == 404:  # no events consumed yet
                return {"user_id": user_id, "albums_completed": 0, "tracks_played": 0, "average_rating": None,
                        "top_genres": [], "top_artists": [], "note": exc.detail}
            raise

    async def get_inbox(self, user_id: str | None = None) -> dict:
        return await self._client.get_inbox(user_id)


class UserSessionService:
    """Gives the agents an identity: logs the configured user in, registering it on the first run."""

    def __init__(self, client: VinylShelfClient, settings: Settings):
        self._client = client
        self._settings = settings

    async def ensure_user(self) -> str:
        if self._settings.default_user_id:
            return self._settings.default_user_id
        username, password = self._settings.agent_username, self._settings.agent_password
        try:
            return (await self._client.login(username, password))["user_id"]
        except ApiError as exc:
            if exc.status_code != 401 or self._settings.keycloak_token_url:  # Keycloak users are not self-registered
                raise
        await self._client.register(username, password)  # first run (or the auth-service lost its in-memory users)
        return (await self._client.login(username, password))["user_id"]
