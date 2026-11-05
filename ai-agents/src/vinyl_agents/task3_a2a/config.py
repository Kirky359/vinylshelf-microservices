from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class A2ASettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    producer_host: str = "127.0.0.1"
    producer_port: int = 9001
    producer_url: str = "http://localhost:9001"
    consumer_host: str = "127.0.0.1"
    consumer_port: int = 9002
    consumer_url: str = "http://localhost:9002"
    delivery_wait_seconds: float = 10.0  # how long the consumer waits for an event to reach its inbox
    a2a_rate_limit_per_minute: int = 60


@lru_cache
def get_a2a_settings() -> A2ASettings:
    return A2ASettings()
