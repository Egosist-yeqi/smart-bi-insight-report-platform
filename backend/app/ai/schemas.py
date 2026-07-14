from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_TIMEOUT_SECONDS = 120


def normalize_base_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Base URL must be an absolute HTTP or HTTPS URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Base URL has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Base URL has an invalid port")

    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class AIProviderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    provider_name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=4096)
    model: str = Field(min_length=1, max_length=160)
    timeout_seconds: int = Field(default=30, ge=1, le=MAX_TIMEOUT_SECONDS)
    enabled: bool = True
    allow_private_network: bool = False

    @field_validator("provider_name", "model")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank")
        return stripped

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return normalize_base_url(value)


class AIProviderTestInput(AIProviderInput):
    """Ephemeral connection test using every current non-secret form field."""

    timeout_seconds: int = Field(ge=1, le=MAX_TIMEOUT_SECONDS)
    enabled: bool
    allow_private_network: bool


class SavedAIProviderTestInput(BaseModel):
    """Empty payload selecting the complete saved provider configuration."""

    model_config = ConfigDict(extra="forbid", strict=True)


AIProviderTestPayload = AIProviderTestInput | SavedAIProviderTestInput


class AIProviderView(BaseModel):
    configured: bool
    ai_mode: str
    provider_name: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout_seconds: int | None = None
    enabled: bool | None = None
    allow_private_network: bool | None = None
    api_key_hint: str | None = None


class AIConnectionResult(BaseModel):
    status: str
    provider: str
    model: str
    latency_ms: int
    enabled: bool
    allow_private_network: bool
