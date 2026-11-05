import time
from datetime import datetime

from vinyl_agents.config import Settings
from vinyl_agents.exceptions import TokenBudgetExceeded
from vinyl_agents.guardrails.json_log import JsonLogFile
from vinyl_agents.llm.schemas import TokenUsage


class TokenBudget:
    """Level 1 guardrail: limits on tokens, number of LLM requests and length of one tool chain.

    The limits are checked BEFORE every LLM call, the usage is recorded AFTER it (from the provider's usage metadata).
    """

    def __init__(self, settings: Settings):
        self._max_session_tokens = settings.max_session_tokens
        self._max_session_requests = settings.max_session_requests
        self._max_request_tokens = settings.max_request_tokens
        self._max_tool_rounds = settings.max_tool_rounds
        self._log = JsonLogFile(settings.token_log_path)
        self._started_at = datetime.now()
        self._started_clock = time.monotonic()
        self._session_tokens = 0
        self._requests: list[dict] = []
        self._request_tokens = 0  # tokens spent on the current user message (all rounds of the chain)

    def begin_user_request(self) -> None:
        self._request_tokens = 0

    def check_before_call(self, round_no: int) -> None:
        if self._session_tokens >= self._max_session_tokens:
            raise TokenBudgetExceeded(f"session token limit reached ({self._session_tokens}/{self._max_session_tokens})")
        if len(self._requests) >= self._max_session_requests:
            raise TokenBudgetExceeded(f"session request limit reached ({len(self._requests)}/{self._max_session_requests})")
        if self._request_tokens >= self._max_request_tokens:
            raise TokenBudgetExceeded(
                f"limit per user request reached ({self._request_tokens}/{self._max_request_tokens} tokens)")
        if round_no > self._max_tool_rounds:
            raise TokenBudgetExceeded(f"tool chain is longer than {self._max_tool_rounds} rounds")

    def record(self, usage: TokenUsage, model: str) -> None:
        self._session_tokens += usage.total_tokens
        self._request_tokens += usage.total_tokens
        self._requests.append({
            "timestamp": datetime.now().isoformat(),
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "model": model,
            "cumulative_tokens": self._session_tokens,
            "cumulative_requests": len(self._requests) + 1,
        })
        self._flush()

    def stats(self) -> dict:
        n = len(self._requests)
        return {
            "session_duration_seconds": round(time.monotonic() - self._started_clock, 3),
            "total_tokens": self._session_tokens,
            "total_requests": n,
            "tokens_remaining": self._max_session_tokens - self._session_tokens,
            "requests_remaining": self._max_session_requests - n,
            "average_tokens_per_request": round(self._session_tokens / n, 1) if n else 0,
        }

    def _flush(self) -> None:
        self._log.write({"session_start": self._started_at.isoformat(), "session_end": datetime.now().isoformat(),
                         "stats": self.stats(), "requests": self._requests})
