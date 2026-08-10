from fastapi.testclient import TestClient


def _assert_validation_contract(response) -> None:
    """Assert the unified 422 error contract."""

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error", "message", "request_id"}
    assert body["error"] == "validation_error"
    assert body["message"] == "Invalid request"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_register_missing_fields_returns_validation_contract(
    client: TestClient,
) -> None:
    response = client.post("/api/auth/register", json={})

    _assert_validation_contract(response)


def test_chat_empty_body_returns_validation_contract(
    auth_client: TestClient, auth_headers
) -> None:
    response = auth_client.post("/api/chat", json={}, headers=auth_headers(auth_client))

    _assert_validation_contract(response)


def test_register_wrong_field_type_returns_validation_contract(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": 12345, "password": "password123"},
    )

    _assert_validation_contract(response)
