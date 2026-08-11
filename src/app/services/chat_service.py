import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.services.deepseek import DeepSeekService, get_deepseek_service
from app.services.history_service import get_recent_messages


@dataclass
class ChatResult:
    """Structured result of a persisted chat exchange."""

    reply: str
    conversation_id: uuid.UUID


def _build_context(
    history: list[ChatMessage],
    message: str,
    max_chars: int,
) -> list[dict[str, str]]:
    """
    Build the DeepSeek messages payload from conversation history.

    Keeps the most recent history messages that fit within the character
    budget, preserving chronological order, then appends the current message.
    """

    budget = max_chars - len(message)
    context: list[dict[str, str]] = []
    for chat_message in reversed(history):
        if len(chat_message.content) > budget:
            break
        context.append({"role": chat_message.role, "content": chat_message.content})
        budget -= len(chat_message.content)
    context.reverse()
    context.append({"role": "user", "content": message})
    return context


async def chat_with_persistence(
    session: AsyncSession,
    user: User,
    message: str,
    model: str | None,
    conversation_id: uuid.UUID | None = None,
    deepseek_service: DeepSeekService | None = None,
) -> ChatResult:
    """
    Persist a user message, call DeepSeek, then persist the assistant reply.

    When conversation_id is omitted a new conversation is created. When it is
    provided the conversation must belong to the user, and its recent messages
    are included as multi-turn context.

    The user message is committed before the DeepSeek call so a failed upstream
    request never loses the user's input; the assistant reply is only committed
    after a successful response.
    """

    if deepseek_service is None:
        deepseek_service = get_deepseek_service()

    settings = get_settings()

    if conversation_id is None:
        conversation_id = uuid.uuid4()
        history: list[ChatMessage] = []
    else:
        history = await get_recent_messages(
            session=session,
            user_id=user.id,
            conversation_id=conversation_id,
            limit=settings.deepseek_history_max_messages,
        )
        if not history:
            raise NotFoundError("Conversation not found.")

    user_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role="user",
        content=message,
        created_at=datetime.now(UTC),
    )
    session.add(user_message)
    await session.commit()

    resolved_model = model or deepseek_service.default_model

    context = _build_context(
        history=history,
        message=message,
        max_chars=settings.deepseek_history_max_chars,
    )
    reply = await deepseek_service.chat_messages(messages=context, model=model)

    assistant_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role="assistant",
        content=reply,
        model=resolved_model,
        created_at=datetime.now(UTC),
    )
    session.add(assistant_message)
    await session.commit()

    return ChatResult(reply=reply, conversation_id=conversation_id)
