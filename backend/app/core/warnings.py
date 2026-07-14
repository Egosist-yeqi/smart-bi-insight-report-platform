from re import fullmatch

from pydantic import BaseModel

from app.core.errors import AppError


class ServiceWarning(BaseModel):
    code: str
    message: str


def ai_service_warning(
    error: Exception,
    *,
    message: str,
    default_code: str = "AI_UNAVAILABLE",
) -> ServiceWarning:
    code = error.code if isinstance(error, AppError) else default_code
    if not isinstance(code, str) or fullmatch(r"AI_[A-Z0-9_]{1,76}", code) is None:
        code = default_code
    return ServiceWarning(code=code, message=message)
