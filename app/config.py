import secrets
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

    ingest_token: str = ""

    line_channel_access_token: str = ""
    line_channel_secret: str = ""
    line_bot_basic_id: str = ""  # e.g. @445lbcso; empty hides the dashboard QR
    line_daily_push_limit: int = 20

    allowed_origins: str = (
        "https://agilenpi.com,"
        "https://www.agilenpi.com,"
        "https://agilenpi-landing-page.pages.dev"
    )

    @property
    def origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


LOCALHOST_RE = r"http://(localhost|127\.0\.0\.1)(:\d+)?"


def ingest_allowed(token: str | None) -> bool:
    """Fail closed: no INGEST_TOKEN configured means nobody may write."""
    if not settings.ingest_token:
        return False
    return bool(token) and secrets.compare_digest(token, settings.ingest_token)


def is_allowed_origin(origin: str | None, host: str | None = None) -> bool:
    if not origin:
        return True  # for postmain or cmd test
    if origin in settings.origin_list:
        return True
    parsed = urlparse(origin)
    if parsed.hostname in ("localhost", "127.0.0.1"):
        return True
    # same-origin: the page was served by this very server (any deploy URL)
    return bool(host) and parsed.netloc == host


settings = Settings()
