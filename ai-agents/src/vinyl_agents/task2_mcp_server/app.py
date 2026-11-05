import logging
import sys

from vinyl_agents.dependencies import CoreContainer
from vinyl_agents.task2_mcp_server.config import McpSettings, get_mcp_settings
from vinyl_agents.task2_mcp_server.guard import McpGuard
from vinyl_agents.task2_mcp_server.server import VinylShelfMcpServer


class McpApplication:
    """Task 2: wires the MCP server (stdio, or MCP_TRANSPORT=streamable-http)."""

    def __init__(self, container: CoreContainer | None = None, settings: McpSettings | None = None):
        self._container = container or CoreContainer()
        self._settings = settings or get_mcp_settings()

    def build(self) -> VinylShelfMcpServer:
        c = self._container
        return VinylShelfMcpServer(c.vinyl_service, c.user_session, McpGuard(self._settings), self._settings)

    def run(self) -> None:
        logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        self.build().run()
