from pydantic_settings import BaseSettings


class Config(BaseSettings):
    service_name: str = "analytics-service"
    service_port: int = 8005
    consul_url: str = "http://consul:8500"
    db_path: str = "/data/analytics.db"
    rabbit_host: str = "rabbitmq"


settings = Config()
