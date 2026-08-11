import asyncio
import uuid
from typing import Self

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.models.chat_message import ChatMessage
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


def _fetch_messages(factory) -> list[ChatMessage]:
    async def fetch() -> list[ChatMessage]:
        async with factory() as session:
            result = await session.scalars(
                select(ChatMessage).order_by(ChatMessage.created_at, ChatMessage.id)
            )
            return list(result.all())

    return asyncio.run(fetch())


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
    data = response.json()
    assert data["reply"] == "AI 回复"
    assert isinstance(uuid.UUID(data["conversation_id"]), uuid.UUID)


def test_chat_persists_user_and_assistant_messages(
    auth_client: TestClient,
    auth_headers,
    db_session_override,
    override_chat_service,
    fake_chat_service,
) -> None:
    override_chat_service(fake_chat_service)

    response = auth_client.post(
        "/api/chat",
        json={"message": "你好", "model": "deepseek-chat"},
        headers=auth_headers(auth_client),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "AI 回复"
    response_conversation_id = uuid.UUID(data["conversation_id"])

    messages = _fetch_messages(db_session_override)

    assert len(messages) == 2
    user_message = next(m for m in messages if m.role == "user")
    assistant_message = next(m for m in messages if m.role == "assistant")
    assert user_message.content == "你好"
    assert assistant_message.content == "AI 回复"
    assert user_message.conversation_id == assistant_message.conversation_id
    assert user_message.conversation_id == response_conversation_id
    assert user_message.user_id == assistant_message.user_id
    assert assistant_message.model == "deepseek-chat"


def test_chat_persists_default_model_when_not_specified(
    auth_client: TestClient,
    auth_headers,
    db_session_override,
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

    messages = _fetch_messages(db_session_override)
    assistant_message = next(m for m in messages if m.role == "assistant")
    assert assistant_message.model == "deepseek-chat"


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


def test_chat_multi_turn_passes_context(
    auth_client: TestClient,
    auth_headers,
    db_session_override,
    override_chat_service,
    fake_chat_service,
) -> None:
    override_chat_service(fake_chat_service)
    headers = auth_headers(auth_client)

    first = auth_client.post(
        "/api/chat",
        json={"message": "第一问"},
        headers=headers,
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = auth_client.post(
        "/api/chat",
        json={"message": "第二问", "conversation_id": conversation_id},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id

    assert fake_chat_service.last_messages == [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "AI 回复"},
        {"role": "user", "content": "第二问"},
    ]

    messages = _fetch_messages(db_session_override)
    assert len(messages) == 4
    assert {m.conversation_id for m in messages} == {uuid.UUID(conversation_id)}


def test_chat_cross_user_conversation_returns_404(
    auth_client: TestClient,
    auth_headers,
    db_session_override,
    override_chat_service,
    fake_chat_service,
) -> None:
    override_chat_service(fake_chat_service)

    alice_headers = auth_headers(auth_client)
    first = auth_client.post(
        "/api/chat",
        json={"message": "你好"},
        headers=alice_headers,
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    auth_client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "password123"},
    )
    login = auth_client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "password123"},
    )
    bob_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = auth_client.post(
        "/api/chat",
        json={"message": "入侵", "conversation_id": conversation_id},
        headers=bob_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"

    messages = _fetch_messages(db_session_override)
    assert len(messages) == 2
    assert all(m.conversation_id == uuid.UUID(conversation_id) for m in messages)


def test_chat_invalid_conversation_id_returns_422(
    auth_client: TestClient,
    auth_headers,
    override_chat_service,
    fake_chat_service,
) -> None:
    override_chat_service(fake_chat_service)
    headers = auth_headers(auth_client)

    response = auth_client.post(
        "/api/chat",
        json={"message": "你好", "conversation_id": "not-a-uuid"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
