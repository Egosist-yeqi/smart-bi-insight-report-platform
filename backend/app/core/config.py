from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Safe configuration failure suitable for startup logs."""


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    app_encryption_key: str
    query_timeout_seconds: int = 5
    ai_default_timeout_seconds: int = 30
    frontend_origin: str = "http://localhost:8080"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("app_encryption_key")
    @classmethod
    def require_valid_fernet_key(cls, value: str) -> str:
        try:
            Fernet(value.encode("ascii"))
        except (UnicodeError, ValueError):
            raise ValueError("must be a valid Fernet key") from None
        return value


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        invalid_fields = {error["loc"][0] for error in exc.errors() if error["loc"]}
        if "app_encryption_key" in invalid_fields:
            message = (
                "Invalid server configuration. Generate a fresh APP_ENCRYPTION_KEY "
                "with Fernet.generate_key() before starting."
            )
        else:
            message = "Invalid server configuration. Review required values in .env before starting."
        raise ConfigurationError(message) from None
