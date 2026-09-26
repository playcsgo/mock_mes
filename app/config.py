from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = ""
    mongo_db_name: str = "line_monitor"

    # alert
    alert_window: int = 50  # 每站看最近 50 筆
    alert_min_samples: int = 20  # 少於 20 筆不判斷，樣本太少不準
    alert_threshold: float = 0.9  # 良率低於 90% 就警報
    alert_cooldown_s: float = 60  # 同一站 60 秒內不重複警報


settings = Settings()
