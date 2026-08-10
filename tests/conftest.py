import asyncio
import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# App settings require a JWT secret; set a test value before importing the app.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-test-secret-key-32")

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
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


@pytest.fixture
def db_session_override(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-test-secret-key-32")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    async def create_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    asyncio.run(engine.dispose())


@pytest.fixture
def auth_client(client: TestClient, db_session_override) -> TestClient:
    return client


@pytest.fixture
def auth_headers() -> Callable[[TestClient], dict[str, str]]:
    """Return a helper that registers a user and yields Bearer auth headers."""

    def _auth_headers(client: TestClient) -> dict[str, str]:
        client.post(
            "/api/auth/register",
            json={"email": "chat@example.com", "password": "password123"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "chat@example.com", "password": "password123"},
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
