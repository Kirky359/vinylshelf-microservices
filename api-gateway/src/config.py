from pydantic_settings import BaseSettings


class Config(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8080
    consul_url: str = "http://consul:8500"

    # CORS: only these origins may call the API from a browser (comma separated)
    cors_origins: str = "https://cad.kpi.ua"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Config()
