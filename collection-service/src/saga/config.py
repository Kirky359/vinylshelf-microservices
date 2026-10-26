from pydantic_settings import BaseSettings


class SagaConfig(BaseSettings):
    saga_timeout_seconds: float = 20


saga_settings = SagaConfig()
