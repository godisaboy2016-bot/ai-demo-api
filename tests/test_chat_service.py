import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.exceptions import DeepSeekError, NotFoundError
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
        self.last_messages: list[dict[str, str]] = []

    async def chat(self, message: str, model: str | None = None) -> str:
        return await self.chat_messages(
            messages=[{"role": "user", "content": message}],
            model=model,
        )

    async def chat_messages(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> str:
        if self.error is not None:
            raise self.error
        self.last_messages = messages
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


async def test_multi_turn_passes_context(db_session, user) -> None:
    conversation_id = uuid.uuid4()
    base = datetime.now(UTC)
    for i, (role, content) in enumerate((("user", "q1"), ("assistant", "a1"))):
        db_session.add(
            ChatMessage(
                user_id=user.id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                created_at=base + timedelta(seconds=i),
            )
        )
    await db_session.commit()

    service = FakeDeepSeekService()
    result = await chat_with_persistence(
        session=db_session,
        user=user,
        message="q2",
        model=None,
        conversation_id=conversation_id,
        deepseek_service=service,
    )

    assert result.conversation_id == conversation_id
    assert service.last_messages == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ]

    messages = await _messages(db_session)
    assert len(messages) == 4


async def test_multi_turn_unknown_conversation_raises_not_found(db_session, user) -> None:
    with pytest.raises(NotFoundError):
        await chat_with_persistence(
            session=db_session,
            user=user,
            message="你好",
            model=None,
            conversation_id=uuid.uuid4(),
            deepseek_service=FakeDeepSeekService(),
        )

    assert await _messages(db_session) == []


async def test_multi_turn_context_keeps_recent_messages(
    db_session, user, monkeypatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_HISTORY_MAX_MESSAGES", "3")
    get_settings.cache_clear()
    try:
        conversation_id = uuid.uuid4()
        base = datetime.now(UTC)
        for i in range(5):
            db_session.add(
                ChatMessage(
                    user_id=user.id,
                    conversation_id=conversation_id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"m-{i}",
                    created_at=base + timedelta(seconds=i),
                )
            )
        await db_session.commit()

        service = FakeDeepSeekService()
        await chat_with_persistence(
            session=db_session,
            user=user,
            message="last",
            model=None,
            conversation_id=conversation_id,
            deepseek_service=service,
        )

        assert service.last_messages == [
            {"role": "user", "content": "m-2"},
            {"role": "assistant", "content": "m-3"},
            {"role": "user", "content": "m-4"},
            {"role": "user", "content": "last"},
        ]
    finally:
        get_settings.cache_clear()


async def test_multi_turn_context_truncated_by_chars(
    db_session, user, monkeypatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_HISTORY_MAX_CHARS", "30")
    get_settings.cache_clear()
    try:
        conversation_id = uuid.uuid4()
        base = datetime.now(UTC)
        for i, content in enumerate(("x" * 25, "y" * 25)):
            db_session.add(
                ChatMessage(
                    user_id=user.id,
                    conversation_id=conversation_id,
                    role="user" if i == 0 else "assistant",
                    content=content,
                    created_at=base + timedelta(seconds=i),
                )
            )
        await db_session.commit()

        service = FakeDeepSeekService()
        await chat_with_persistence(
            session=db_session,
            user=user,
            message="z",
            model=None,
            conversation_id=conversation_id,
            deepseek_service=service,
        )

        assert service.last_messages == [
            {"role": "assistant", "content": "y" * 25},
            {"role": "user", "content": "z"},
        ]
    finally:
        get_settings.cache_clear()


async def test_multi_turn_failure_persists_user_message_only(db_session, user) -> None:
    conversation_id = uuid.uuid4()
    base = datetime.now(UTC)
    for i, (role, content) in enumerate((("user", "q1"), ("assistant", "a1"))):
        db_session.add(
            ChatMessage(
                user_id=user.id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                created_at=base + timedelta(seconds=i),
            )
        )
    await db_session.commit()

    service = FakeDeepSeekService(error=DeepSeekError("upstream failure"))

    with pytest.raises(DeepSeekError):
        await chat_with_persistence(
            session=db_session,
            user=user,
            message="q2",
            model=None,
            conversation_id=conversation_id,
            deepseek_service=service,
        )

    messages = await _messages(db_session)
    assert len(messages) == 3
    user_q2 = next(m for m in messages if m.content == "q2")
    assert user_q2.role == "user"
    assert user_q2.conversation_id == conversation_id
    assert {m.role for m in messages if m.content != "q2"} == {"user", "assistant"}
