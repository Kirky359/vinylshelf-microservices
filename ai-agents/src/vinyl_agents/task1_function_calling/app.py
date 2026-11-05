import sys

from vinyl_agents.agent.dependencies import AgentContainer
from vinyl_agents.exceptions import AgentError
from vinyl_agents.task1_function_calling.console import ConsoleController, ConsolePrinter


class FunctionCallingApplication:
    """Task 1: logs the user in, builds the agent and starts the console dialogue."""

    def __init__(self, container: AgentContainer | None = None):
        self._container = container or AgentContainer()

    async def run(self) -> None:
        try:
            user_id = await self._container.user_session.ensure_user()
            print(f"👤 Agent works on behalf of user {user_id}")
            agent = self._container.agent(listener=ConsolePrinter())
            await ConsoleController(agent, user_id).run()
        except AgentError as exc:
            sys.exit(f"❌ {exc.message}")
        finally:
            await self._container.close()
