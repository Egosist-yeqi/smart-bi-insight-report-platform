from cryptography.fernet import Fernet

import pytest

from app.core.crypto import (
    SecretEncryptionError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)
from app.core.config import ConfigurationError, get_settings


def test_secret_round_trip_and_masking():
    fernet_key = Fernet.generate_key().decode("ascii")

    encrypted = encrypt_secret("sk-test-123456789", fernet_key)

    assert encrypted != "sk-test-123456789"
    assert decrypt_secret(encrypted, fernet_key) == "sk-test-123456789"
    assert mask_secret("sk-test-123456789") == "sk-t...6789"


def test_invalid_master_key_is_never_exposed_in_an_error():
    invalid_master_key = "not-a-fernet-key"

    with pytest.raises(SecretEncryptionError) as error:
        encrypt_secret("sk-test-123456789", invalid_master_key)

    assert invalid_master_key not in str(error.value)


@pytest.mark.parametrize(
    ("secret", "expected"),
    [
        ("abc", "***"),
        ("abcde", "a...e"),
        ("test-key", "te...ey"),
    ],
)
def test_short_secret_masking_never_reveals_overlapping_characters(secret, expected):
    assert mask_secret(secret) == expected


def test_invalid_configured_master_key_has_a_sanitized_startup_error(monkeypatch):
    invalid_master_key = "not-a-fernet-key"
    monkeypatch.setenv("APP_ENCRYPTION_KEY", invalid_master_key)
    get_settings.cache_clear()

    with pytest.raises(ConfigurationError) as error:
        get_settings()

    assert invalid_master_key not in str(error.value)
    get_settings.cache_clear()
