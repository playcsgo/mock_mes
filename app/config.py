from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = ""
    mongo_db_name: str = "line_monitor"

    # alert
    alert_window: int = 50  # look at the last 50 results per station
    alert_min_samples: int = 20  # below this, too few samples to judge
    alert_threshold: float = 0.9  # alert when yield drops under 90%
    alert_cooldown_s: float = 60  # do not re-alert the same station within 60s


settings = Settings()
