import asyncio
import json
import sys

from vinyl_agents.task3_a2a.config import get_a2a_settings
from vinyl_agents.task3_a2a.remote_client import RemoteAgentClient


class A2AConsoleClient:
    """Talks to an A2A agent from the terminal: prints its Agent Card, then sends text or a JSON skill call.

    python -m vinyl_agents.task3_a2a.client_cli consumer '{"skill": "get_user_dashboard", "arguments": {"user_id": "..."}}'
    python -m vinyl_agents.task3_a2a.client_cli producer "Add album a1 for user <id>"
    """

    def __init__(self, agent_url: str):
        self._agent = RemoteAgentClient(agent_url)

    async def run(self, request: str) -> None:
        card = await self._agent.card()
        print(f"🪪 {card.name} v{card.version} @ {card.url}")
        for skill in card.skills:
            print(f"   • {skill.id}: {skill.description[:90]}")
        payload = json.loads(request) if request.lstrip().startswith("{") else request
        print(f"\n📨 Sending: {request}")
        state, data, text = await self._agent.send(payload)
        print(f"\n📌 Task state: {state}\n💬 {text}")
        if data is not None:
            print("📦 Artifact:\n" + json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    settings = get_a2a_settings()
    urls = {"producer": settings.producer_url, "consumer": settings.consumer_url}
    if len(sys.argv) != 3 or sys.argv[1] not in urls:
        sys.exit(__doc__ or A2AConsoleClient.__doc__)
    asyncio.run(A2AConsoleClient(urls[sys.argv[1]]).run(sys.argv[2]))
