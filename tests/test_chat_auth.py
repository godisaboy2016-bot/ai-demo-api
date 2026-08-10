from fastapi.testclient import TestClient


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
