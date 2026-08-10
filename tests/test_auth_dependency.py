from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token


def _register_and_login(client: TestClient) -> str:
    """Register a user and return an access token."""

    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    return response.json()["access_token"]


def test_me_returns_current_user(auth_client: TestClient) -> None:
    token = _register_and_login(auth_client)

    response = auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["is_active"] is True
    assert body["id"]
    assert body["created_at"]
    assert "hashed_password" not in body


def test_me_without_token_returns_401(auth_client: TestClient) -> None:
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_me_with_invalid_token_returns_401(auth_client: TestClient) -> None:
    response = auth_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"


def test_me_with_token_for_unknown_user_returns_401(auth_client: TestClient) -> None:
    token = create_access_token(uuid4())

    response = auth_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
