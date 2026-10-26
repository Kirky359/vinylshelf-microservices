from pydantic_settings import BaseSettings


class Config(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8080
    consul_url: str = "http://consul:8500"


settings = Config()
