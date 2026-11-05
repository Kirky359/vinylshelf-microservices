import uvicorn
from a2a.server.agent_execution import AgentExecutor
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard


class AgentApplication:
    """An A2A server: Agent Card + JSON-RPC endpoint (message/send, tasks/get, tasks/cancel) on top of FastAPI."""

    def __init__(self, card: AgentCard, executor: AgentExecutor):
        self._card = card
        self._executor = executor

    def build(self):
        handler = DefaultRequestHandler(agent_executor=self._executor, task_store=InMemoryTaskStore())
        return A2AFastAPIApplication(agent_card=self._card, http_handler=handler).build()

    def run(self, host: str, port: int) -> None:
        uvicorn.run(self.build(), host=host, port=port)
