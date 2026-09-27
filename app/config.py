from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = ""
    mongo_db_name: str = "line_monitor"

    alert_window: int = 50
    alert_min_samples: int = 20
    alert_threshold: float = 0.9
    alert_cooldown_s: float = 60


settings = Settings()
