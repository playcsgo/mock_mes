from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = ""
    mongo_db_name: str = "line_monitor"

    alert_window: int = 50
    alert_min_samples: int = 20
    alert_threshold: float = 0.9
    alert_cooldown_s: float = 60

    allowed_origins: str = (
        "https://agilenpi.com,"
        "https://www.agilenpi.com,"
        "https://agilenpi-landing-page.pages.dev"
    )

    @property
    def origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


LOCALHOST_RE = r"http://(localhost|127\.0\.0\.1)(:\d+)?"


def is_allowed_origin(origin: str | None) -> bool:
    if not origin:
        return True  # for postmain or cmd test
    if origin in settings.origin_list:
        return True
    return urlparse(origin).hostname in ("localhost", "127.0.0.1")


settings = Settings()
