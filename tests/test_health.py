import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    settings = get_settings()
    assert body["status"] == "ok"
    assert body["service"] == settings.app_name
    assert body["version"] == settings.app_version
    assert body["environment"] == settings.environment


def test_health_content_type_is_json(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["content-type"].startswith("application/json")


def test_health_reflects_environment_overrides(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("APP_APP_NAME", "ai-demo-api-staging")
    monkeypatch.setenv("APP_APP_VERSION", "2.0.0")
    try:
        response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "production"
    assert body["service"] == "ai-demo-api-staging"
    assert body["version"] == "2.0.0"
