from pydantic_settings import BaseSettings


class Config(BaseSettings):
    service_name: str = "auth-service"
    service_port: int = 8000
    consul_url: str = "http://consul:8500"
    rabbit_host: str = "rabbitmq"


settings = Config()
