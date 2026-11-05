import time
from collections import deque

from vinyl_agents.exceptions import RateLimitExceeded


class SlidingWindowRateLimiter:
    """At most `max_calls` calls per `window_seconds` (used by the MCP server and the A2A agents)."""

    def __init__(self, max_calls: int, window_seconds: float = 60.0):
        self._max_calls = max_calls
        self._window = window_seconds
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > self._window:
            self._calls.popleft()
        if len(self._calls) >= self._max_calls:
            raise RateLimitExceeded(f"rate limit: {self._max_calls} calls per {int(self._window)} s")
        self._calls.append(now)
