import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import User

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


async def test_user_model_can_be_created(db_session) -> None:
    user = User(
        email="alice@example.com",
        hashed_password="hashed-placeholder",
    )
    db_session.add(user)
    await db_session.commit()

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True

    await db_session.refresh(user)
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_user_can_be_inserted_and_read(db_session) -> None:
    user = User(
        email="bob@example.com",
        hashed_password="hashed-placeholder",
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.get(User, user.id)

    assert result is not None
    assert result.email == "bob@example.com"
    assert result.hashed_password == "hashed-placeholder"
    assert result.is_active is True


async def test_user_email_unique(db_session) -> None:
    db_session.add(User(email="dup@example.com", hashed_password="first"))
    await db_session.commit()

    db_session.add(User(email="dup@example.com", hashed_password="second"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
