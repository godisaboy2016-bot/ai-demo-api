from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_chat_without_token_returns_401(
    auth_client: TestClient, override_chat_service, fake_chat_service
) -> None:
    override_chat_service(fake_chat_service)

    response = auth_client.post("/api/chat", json={"message": "你好"})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_chat_with_invalid_token_returns_401(
    auth_client: TestClient, override_chat_service, fake_chat_service
) -> None:
    override_chat_service(fake_chat_service)

    response = auth_client.post(
        "/api/chat",
        json={"message": "你好"},
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_chat_with_expired_token_returns_401(
    auth_client: TestClient, override_chat_service, fake_chat_service
) -> None:
    override_chat_service(fake_chat_service)
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "type": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = auth_client.post(
        "/api/chat",
        json={"message": "你好"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_chat_with_valid_token_returns_200(
    auth_client: TestClient,
    auth_headers,
    override_chat_service,
    fake_chat_service,
) -> None:
    override_chat_service(fake_chat_service)

    response = auth_client.post(
        "/api/chat",
        json={"message": "你好"},
        headers=auth_headers(auth_client),
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "AI 回复"}
