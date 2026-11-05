import asyncio
import json

from vinyl_agents.dependencies import CoreContainer
from vinyl_agents.task3_a2a.config import A2ASettings, get_a2a_settings
from vinyl_agents.task3_a2a.remote_client import RemoteAgentClient


class A2ADemo:
    """Scenario without an LLM (structured skill calls): the user talks only to the Consumer agent, which asks the
    Producer agent over A2A to produce events and checks that they arrived. Needs both agents and the lab 3 stack."""

    def __init__(self, container: CoreContainer | None = None, settings: A2ASettings | None = None):
        self._container = container or CoreContainer()
        self._settings = settings or get_a2a_settings()
        self._consumer = RemoteAgentClient(self._settings.consumer_url)

    async def run(self, album_id: str = "a1", tracks: int = 5) -> None:
        user_id = await self._container.user_session.ensure_user()
        print(f"👤 user {user_id}")
        for card_url in (self._settings.producer_url, self._settings.consumer_url):
            card = await RemoteAgentClient(card_url).card()
            print(f"🪪 {card.name}: skills = {[s.id for s in card.skills]}")
        steps = [("album_added", {}), ("progress_updated", {"tracks_played": tracks}), ("album_completed", {})]
        for event, extra in steps:
            print(f"\n➡️  consumer.request_event({event})")
            state, data, text = await self._consumer.send(
                {"skill": "request_event", "arguments": {"event": event, "user_id": user_id, "album_id": album_id, **extra}})
            print(f"   task: {state}; {text}")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        await self._container.close()


if __name__ == "__main__":
    asyncio.run(A2ADemo().run())
