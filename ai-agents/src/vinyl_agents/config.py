from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration. Every field can be set via env / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # REST API of lab 3
    gateway_url: str = "http://localhost:8080"
    http_timeout_seconds: float = 10.0
    agent_username: str = "artem@pm.me"
    agent_password: str = "change-me"
    default_user_id: str | None = None  # skips the login step

    # LLM
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: float = 30.0
    gemini_thinking_budget: int | None = None  # set 0 on 2.5 models to disable hidden reasoning
    prompt_style: str = "non_reasoning"  # or "reasoning", see llm/prompts.py

    # Level 1 guardrails: token / request limits
    max_session_tokens: int = 20_000
    max_session_requests: int = 30
    max_request_tokens: int = 8_000
    max_tool_rounds: int = 8  # LLM calls per user request (the last one writes the answer)
    max_tool_calls_per_round: int = 4
    max_output_tokens: int = 512
    max_history_messages: int = 24
    token_log_path: Path = Path("logs/token_usage.json")

    # Level 3 guardrails: prompt injection / validation
    max_user_message_chars: int = 500
    max_tool_output_chars: int = 4_000
    injection_log_path: Path = Path("logs/injection_attempts.json")

    saga_wait_seconds: float = 25.0  # how long complete_album waits for the SAGA result


@lru_cache
def get_settings() -> Settings:
    return Settings()
