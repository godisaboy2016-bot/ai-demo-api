from fastapi.testclient import TestClient


def test_register_success(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["is_active"] is True
    assert body["id"]
    assert body["created_at"]
    assert "hashed_password" not in body


def test_register_duplicate_email_returns_409(auth_client: TestClient) -> None:
    payload = {"email": "alice@example.com", "password": "password123"}
    assert auth_client.post("/api/auth/register", json=payload).status_code == 201

    response = auth_client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"] == "user_already_exists"


def test_register_short_password_returns_422(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_login_success_returns_token(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


def test_login_wrong_password_returns_401(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


def test_login_unknown_user_returns_401(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"
