import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import AgentCard, DataPart, Message, Part, Role, TextPart


def user_message(payload: dict | str) -> Message:
    part = TextPart(text=payload) if isinstance(payload, str) else DataPart(data=payload)
    return Message(role=Role.user, parts=[Part(root=part)], message_id=uuid.uuid4().hex)


class RemoteAgentClient:
    """A2A client: reads the Agent Card of another agent and sends it tasks."""

    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None):
        self._base_url = base_url
        self._http = http or httpx.AsyncClient(timeout=60)

    async def card(self) -> AgentCard:
        return await A2ACardResolver(self._http, self._base_url).get_agent_card()

    async def send(self, payload: dict | str) -> tuple[str, dict | None, str]:
        """Returns (task state, data of the first artifact, status text)."""
        client = ClientFactory(ClientConfig(streaming=False, httpx_client=self._http)).create(await self.card())
        state, data, text = "unknown", None, ""
        async for event in client.send_message(user_message(payload)):
            task = event[0] if isinstance(event, tuple) else None
            if task is None:
                text = "".join(p.root.text for p in event.parts if isinstance(p.root, TextPart))
                state = "message"
                continue
            state = task.status.state.value
            if task.status.message:
                text = "".join(p.root.text for p in task.status.message.parts if isinstance(p.root, TextPart))
            for artifact in task.artifacts or []:
                for part in artifact.parts:
                    if isinstance(part.root, DataPart):
                        data = part.root.data
        return state, data, text
