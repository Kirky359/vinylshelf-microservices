from pydantic_settings import BaseSettings


class Config(BaseSettings):
    service_name: str = "catalog-service"
    service_port: int = 8004
    consul_url: str = "http://consul:8500"


settings = Config()
