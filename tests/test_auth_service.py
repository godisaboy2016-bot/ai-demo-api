import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.exceptions import AuthError, ConflictError
from app.db.base import Base
from app.services.auth_service import authenticate_user, register_user

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


async def test_register_user_succeeds(db_session) -> None:
    user = await register_user(db_session, "alice@example.com", "password123")

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.hashed_password != "password123"
    assert user.hashed_password.startswith("$2")
    assert user.is_active is True


async def test_register_duplicate_email_raises_conflict(db_session) -> None:
    await register_user(db_session, "alice@example.com", "password123")

    with pytest.raises(ConflictError) as exc_info:
        await register_user(db_session, "alice@example.com", "password456")

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "user_already_exists"


async def test_register_race_duplicate_email_raises_conflict(
    db_session, monkeypatch
) -> None:
    await register_user(db_session, "alice@example.com", "password123")

    async def scalar_none(*args, **kwargs):
        return None

    monkeypatch.setattr(db_session, "scalar", scalar_none)

    with pytest.raises(ConflictError) as exc_info:
        await register_user(db_session, "alice@example.com", "password456")

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "user_already_exists"


async def test_register_normalizes_email_lowercase(db_session) -> None:
    user = await register_user(db_session, "  Alice@Example.COM  ", "password123")

    assert user.email == "alice@example.com"


async def test_authenticate_user_succeeds(db_session) -> None:
    await register_user(db_session, "alice@example.com", "password123")

    user = await authenticate_user(db_session, "alice@example.com", "password123")

    assert user.email == "alice@example.com"


async def test_authenticate_wrong_password_raises_auth_error(db_session) -> None:
    await register_user(db_session, "alice@example.com", "password123")

    with pytest.raises(AuthError) as exc_info:
        await authenticate_user(db_session, "alice@example.com", "wrong-password")

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "invalid_credentials"


async def test_authenticate_unknown_user_raises_auth_error(db_session) -> None:
    with pytest.raises(AuthError) as exc_info:
        await authenticate_user(db_session, "nobody@example.com", "password123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "invalid_credentials"
