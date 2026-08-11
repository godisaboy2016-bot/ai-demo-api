import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.exceptions import DeepSeekError
from app.db.base import Base
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.services.auth_service import register_user
from app.services.chat_service import chat_with_persistence

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeDeepSeekService:
    """In-memory stand-in for DeepSeekService used in service tests."""

    def __init__(
        self,
        reply: str = "AI 回复",
        error: Exception | None = None,
        default_model: str = "deepseek-chat",
    ) -> None:
        self.reply = reply
        self.error = error
        self.default_model = default_model

    async def chat(self, message: str, model: str | None = None) -> str:
        if self.error is not None:
            raise self.error
        return self.reply


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


@pytest.fixture
async def user(db_session) -> User:
    return await register_user(db_session, "chat-service@example.com", "password123")


async def _messages(session) -> list[ChatMessage]:
    result = await session.scalars(
        select(ChatMessage).order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return list(result.all())


async def test_user_message_is_persisted(db_session, user) -> None:
    result = await chat_with_persistence(
        session=db_session,
        user=user,
        message="你好",
        model=None,
        deepseek_service=FakeDeepSeekService(),
    )

    assert result.reply == "AI 回复"
    assert isinstance(result.conversation_id, uuid.UUID)

    messages = await _messages(db_session)
    user_message = next(m for m in messages if m.role == "user")
    assert user_message.user_id == user.id
    assert user_message.content == "你好"
    assert user_message.role == "user"
    assert user_message.model is None
    assert user_message.conversation_id is not None


async def test_assistant_message_is_persisted(db_session, user) -> None:
    await chat_with_persistence(
        session=db_session,
        user=user,
        message="你好",
        model="deepseek-chat",
        deepseek_service=FakeDeepSeekService(reply="AI 回复"),
    )

    messages = await _messages(db_session)
    assistant_message = next(m for m in messages if m.role == "assistant")
    assert assistant_message.user_id == user.id
    assert assistant_message.content == "AI 回复"
    assert assistant_message.model == "deepseek-chat"


async def test_messages_share_conversation_id(db_session, user) -> None:
    result = await chat_with_persistence(
        session=db_session,
        user=user,
        message="你好",
        model=None,
        deepseek_service=FakeDeepSeekService(),
    )

    messages = await _messages(db_session)
    assert len(messages) == 2
    assert {m.role for m in messages} == {"user", "assistant"}

    user_message = next(m for m in messages if m.role == "user")
    assistant_message = next(m for m in messages if m.role == "assistant")
    assert user_message.conversation_id == assistant_message.conversation_id
    assert isinstance(user_message.conversation_id, uuid.UUID)
    assert result.conversation_id == user_message.conversation_id


async def test_assistant_message_uses_default_model_when_not_specified(
    db_session, user
) -> None:
    await chat_with_persistence(
        session=db_session,
        user=user,
        message="你好",
        model=None,
        deepseek_service=FakeDeepSeekService(),
    )

    messages = await _messages(db_session)
    assistant_message = next(m for m in messages if m.role == "assistant")
    assert assistant_message.model == "deepseek-chat"


async def test_deepseek_failure_persists_user_message_only(db_session, user) -> None:
    service = FakeDeepSeekService(error=DeepSeekError("upstream failure"))

    with pytest.raises(DeepSeekError):
        await chat_with_persistence(
            session=db_session,
            user=user,
            message="你好",
            model=None,
            deepseek_service=service,
        )

    messages = await _messages(db_session)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "你好"
