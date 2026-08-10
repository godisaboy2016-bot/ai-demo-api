from fastapi.testclient import TestClient


def _assert_contract(response, error: str, status_code: int) -> None:
    """Assert the unified error contract for default exceptions."""

    assert response.status_code == status_code
    body = response.json()
    assert set(body) == {"error", "message", "request_id"}
    assert body["error"] == error
    assert body["message"]
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_register_missing_fields_returns_validation_contract(
    client: TestClient,
) -> None:
    response = client.post("/api/auth/register", json={})

    _assert_contract(response, "validation_error", 422)


def test_chat_empty_body_returns_validation_contract(
    auth_client: TestClient, auth_headers
) -> None:
    response = auth_client.post("/api/chat", json={}, headers=auth_headers(auth_client))

    _assert_contract(response, "validation_error", 422)


def test_register_wrong_field_type_returns_validation_contract(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": 12345, "password": "password123"},
    )

    _assert_contract(response, "validation_error", 422)


def test_unknown_route_returns_404_contract(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    _assert_contract(response, "not_found", 404)


def test_wrong_method_returns_405_contract(client: TestClient) -> None:
    response = client.delete("/api/auth/me")

    _assert_contract(response, "method_not_allowed", 405)
