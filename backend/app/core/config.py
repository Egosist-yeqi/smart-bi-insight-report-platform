from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    app_encryption_key: str
    query_timeout_seconds: int = 5
    ai_default_timeout_seconds: int = 30
    frontend_origin: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
