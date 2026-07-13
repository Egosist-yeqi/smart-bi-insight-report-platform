from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AppError


class SecretDecryptionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_CONFIGURATION_INVALID",
            message="AI 配置无法解密，请重新保存配置。",
            status_code=500,
        )


class SecretEncryptionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_CONFIGURATION_INVALID",
            message="AI 加密配置无效，请检查应用密钥。",
            status_code=500,
        )


def encrypt_secret(secret: str, fernet_key: str) -> str:
    return _fernet(fernet_key).encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(encrypted_secret: str, fernet_key: str) -> str:
    try:
        return _fernet(fernet_key).decrypt(
            encrypted_secret.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise SecretDecryptionError() from None


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 4:
        return "*" * len(secret)
    visible = min(4, max(1, len(secret) // 3))
    return f"{secret[:visible]}...{secret[-visible:]}"


def _fernet(fernet_key: str) -> Fernet:
    try:
        return Fernet(fernet_key.encode("ascii"))
    except (AttributeError, UnicodeError, ValueError):
        raise SecretEncryptionError() from None
