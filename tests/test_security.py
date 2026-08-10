from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-test-secret-key-32")
    yield
    get_settings.cache_clear()


def test_hash_password_cannot_be_reversed() -> None:
    hashed = hash_password("super-secret")

    assert hashed != "super-secret"
    assert hashed.startswith("$2")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct-password")

    assert verify_password("correct-password", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-password")

    assert verify_password("wrong-password", hashed) is False


def test_create_access_token_succeeds(jwt_settings) -> None:
    token = create_access_token("user-123")

    assert isinstance(token, str)
    assert token.count(".") == 2


def test_decode_access_token_succeeds(jwt_settings) -> None:
    token = create_access_token("user-123")

    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload


def test_decode_access_token_rejects_expired(jwt_settings) -> None:
    settings = get_settings()
    payload = {
        "sub": "user-123",
        "iat": datetime.now(UTC) - timedelta(hours=1),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
        "type": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_access_token_rejects_tampered(jwt_settings) -> None:
    token = create_access_token("user-123")
    tampered = token[:-1] + ("w" if token[-1] != "w" else "g")

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(tampered)
