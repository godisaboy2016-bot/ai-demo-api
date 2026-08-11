import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.chat_message import ChatMessage
from app.models.user import User

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


async def _create_user(session) -> User:
    user = User(
        email="alice@example.com",
        hashed_password="hashed-placeholder",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_chat_message_can_be_created(db_session) -> None:
    user = await _create_user(db_session)
    conversation_id = uuid.uuid4()

    user_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role="user",
        content="你好",
    )
    assistant_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role="assistant",
        content="你好！有什么可以帮你？",
        model="deepseek-chat",
    )
    db_session.add_all([user_message, assistant_message])
    await db_session.commit()
    await db_session.refresh(user_message)
    await db_session.refresh(assistant_message)

    assert isinstance(user_message.id, uuid.UUID)
    assert user_message.user_id == user.id
    assert user_message.conversation_id == conversation_id
    assert user_message.role == "user"
    assert user_message.model is None
    assert user_message.created_at is not None
    assert assistant_message.role == "assistant"
    assert assistant_message.model == "deepseek-chat"


async def test_chat_messages_queried_by_user_ordered(db_session) -> None:
    user = await _create_user(db_session)
    base_time = datetime.now(UTC)

    for i in range(3):
        db_session.add(
            ChatMessage(
                user_id=user.id,
                conversation_id=uuid.uuid4(),
                role="user",
                content=f"message-{i}",
                created_at=base_time + timedelta(seconds=i),
            )
        )
    await db_session.commit()

    result = await db_session.scalars(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )

    messages = result.all()
    assert len(messages) == 3
    assert [m.content for m in messages] == ["message-0", "message-1", "message-2"]


async def test_invalid_role_rejected(db_session) -> None:
    user = await _create_user(db_session)
    db_session.add(
        ChatMessage(
            user_id=user.id,
            conversation_id=uuid.uuid4(),
            role="system",
            content="should fail",
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_user_relationship_loads_messages(db_session) -> None:
    user = await _create_user(db_session)
    db_session.add(
        ChatMessage(
            user_id=user.id,
            conversation_id=uuid.uuid4(),
            role="user",
            content="你好",
        )
    )
    await db_session.commit()

    loaded = await db_session.scalar(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.chat_messages))
    )

    assert loaded is not None
    assert len(loaded.chat_messages) == 1
    assert loaded.chat_messages[0].content == "你好"
