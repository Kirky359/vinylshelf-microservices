from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_transport: str = "stdio"  # stdio | streamable-http
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_read_only: bool = False
    mcp_rate_limit_per_minute: int = 30
    mcp_max_response_chars: int = 8_000


@lru_cache
def get_mcp_settings() -> McpSettings:
    return McpSettings()
