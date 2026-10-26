from pydantic_settings import BaseSettings


class Config(BaseSettings):
    service_name: str = "collection-service"
    service_port: int = 8001
    consul_url: str = "http://consul:8500"
    db_path: str = "/data/collection.db"
    rabbit_host: str = "rabbitmq"


settings = Config()
