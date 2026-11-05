import json
import logging
from collections.abc import Awaitable, Callable

from vinyl_agents.exceptions import AgentError, ApiError, ReadOnlyMode
from vinyl_agents.guardrails.rate_limiter import SlidingWindowRateLimiter
from vinyl_agents.task2_mcp_server.config import McpSettings

log = logging.getLogger("vinyl_agents.mcp")  # stderr only: on the stdio transport stdout carries the protocol


class McpGuard:
    """Guardrails of the MCP server: read-only mode, rate limit, error mapping, size limit, audit log."""

    def __init__(self, settings: McpSettings):
        self._read_only = settings.mcp_read_only
        self._limiter = SlidingWindowRateLimiter(settings.mcp_rate_limit_per_minute)
        self._max_chars = settings.mcp_max_response_chars

    async def run(self, tool: str, mutating: bool, call: Callable[[], Awaitable[dict]]) -> dict:
        if mutating and self._read_only:
            raise ReadOnlyMode(f"'{tool}' changes data, but the server runs in read-only mode")
        self._limiter.acquire()
        log.info("tool call: %s (mutating=%s)", tool, mutating)
        try:
            result = await call()
        except ApiError as exc:
            log.warning("tool %s failed: %s", tool, exc.message)
            raise AgentError(f"VinylShelf API error: {exc.message}") from exc
        return self._limit_size(result)

    def _limit_size(self, result: dict) -> dict:
        text = json.dumps(result, ensure_ascii=False)
        if len(text) <= self._max_chars:
            return result
        return {"truncated": True, "preview": text[: self._max_chars]}
