from pydantic_settings import BaseSettings


class AnalyticsConfig(BaseSettings):
    fail_every_n: int = 3   # simulated error: every N-th album_completed event fails (0 = off)


analytics_settings = AnalyticsConfig()
