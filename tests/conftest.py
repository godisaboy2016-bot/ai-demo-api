from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.deepseek import get_deepseek_service


class FakeDeepSeekService:
    """In-memory stand-in for DeepSeekService used in API tests."""

    def __init__(self, reply: str = "AI 回复", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error

    async def chat(self, message: str, model: str | None = None) -> str:
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def fake_chat_service() -> FakeDeepSeekService:
    return FakeDeepSeekService()


@pytest.fixture
def override_chat_service() -> Iterator[Callable[[object], None]]:
    def set_service(service: object) -> None:
        app.dependency_overrides[get_deepseek_service] = lambda: service

    yield set_service
    app.dependency_overrides.clear()
