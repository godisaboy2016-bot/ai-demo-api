import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


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
