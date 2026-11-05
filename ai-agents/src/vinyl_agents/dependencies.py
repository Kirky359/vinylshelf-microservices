from functools import cached_property

from vinyl_agents.config import Settings, get_settings
from vinyl_agents.vinylshelf.client import VinylShelfClient
from vinyl_agents.vinylshelf.service import UserSessionService, VinylShelfService


class CoreContainer:
    """Dependencies every application needs: settings, REST client and the VinylShelf use cases.
    Each object is created once, lazily. Tests pass their own settings or client."""

    def __init__(self, settings: Settings | None = None, client: VinylShelfClient | None = None):
        self.settings = settings or get_settings()
        self._client = client

    @cached_property
    def client(self) -> VinylShelfClient:
        return self._client or VinylShelfClient(self.settings)

    @cached_property
    def vinyl_service(self) -> VinylShelfService:
        return VinylShelfService(self.client, self.settings)

    @cached_property
    def user_session(self) -> UserSessionService:
        return UserSessionService(self.client, self.settings)

    async def close(self) -> None:
        await self.client.aclose()
