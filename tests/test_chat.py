import asyncio
from typing import Self

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services.deepseek import DeepSeekError, DeepSeekService


class FakeAsyncClient:
    """Fake httpx.AsyncClient that returns a fixed response or raises."""

    def __init__(self, response: httpx.Response | Exception) -> None:
        self._response = response
        self.last_url: str | None = None
        self.last_json: dict | None = None
        self.last_headers: dict | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(
        self, url: str, json: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        self.last_url = url
        self.last_json = json
        self.last_headers = headers
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def make_service(api_key: str | None = "test-key") -> DeepSeekService:
    settings = Settings.model_construct(
        deepseek_api_key=api_key,
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-chat",
        deepseek_timeout_seconds=60.0,
    )
    return DeepSeekService(settings)


def test_settings_read_deepseek_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    settings = Settings()

    assert settings.deepseek_api_key == "sk-env-test"
    assert settings.deepseek_model == "deepseek-reasoner"


def test_chat_returns_ai_reply(
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


def test_chat_missing_message_returns_422(
    auth_client: TestClient, auth_headers
) -> None:
    response = auth_client.post("/api/chat", json={}, headers=auth_headers(auth_client))

    assert response.status_code == 422


def test_chat_empty_message_returns_422(
    auth_client: TestClient, auth_headers
) -> None:
    response = auth_client.post(
        "/api/chat",
        json={"message": ""},
        headers=auth_headers(auth_client),
    )

    assert response.status_code == 422


def test_chat_content_type_is_json(
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

    assert response.headers["content-type"].startswith("application/json")


def test_chat_service_error_maps_to_502(
    auth_client: TestClient,
    auth_headers,
    override_chat_service,
    fake_chat_service,
) -> None:
    fake_chat_service.error = DeepSeekError("upstream failure")
    override_chat_service(fake_chat_service)
    response = auth_client.post(
        "/api/chat",
        json={"message": "你好"},
        headers=auth_headers(auth_client),
    )

    assert response.status_code == 502


def test_chat_missing_api_key_returns_503(
    auth_client: TestClient, auth_headers, override_chat_service
) -> None:
    override_chat_service(make_service(api_key=None))
    response = auth_client.post(
        "/api/chat",
        json={"message": "你好"},
        headers=auth_headers(auth_client),
    )

    assert response.status_code == 503


def test_service_sends_request_and_parses_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(
        httpx.Response(200, json={"choices": [{"message": {"content": "AI 你好"}}]})
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    reply = asyncio.run(make_service().chat("你好"))

    assert reply == "AI 你好"
    assert fake_client.last_url == "https://api.deepseek.com/chat/completions"
    assert fake_client.last_json == {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False,
    }
    assert fake_client.last_headers["Authorization"] == "Bearer test-key"


def test_service_uses_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(
        httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    asyncio.run(make_service().chat("hi", model="deepseek-reasoner"))

    assert fake_client.last_json["model"] == "deepseek-reasoner"


def test_service_raises_on_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(httpx.Response(401, text="invalid api key"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with pytest.raises(DeepSeekError) as exc_info:
        asyncio.run(make_service().chat("你好"))

    assert exc_info.value.status_code == 502


def test_service_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(httpx.TimeoutException("request timed out"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with pytest.raises(DeepSeekError) as exc_info:
        asyncio.run(make_service().chat("你好"))

    assert exc_info.value.status_code == 504


def test_service_raises_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(httpx.ConnectError("connection refused"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with pytest.raises(DeepSeekError) as exc_info:
        asyncio.run(make_service().chat("你好"))

    assert exc_info.value.status_code == 502


def test_service_raises_on_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeAsyncClient(httpx.Response(200, json={"choices": []}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    with pytest.raises(DeepSeekError):
        asyncio.run(make_service().chat("你好"))
