import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.user import User
from app.services.deepseek import DeepSeekService, get_deepseek_service


@dataclass
class ChatResult:
    """Structured result of a persisted chat exchange."""

    reply: str
    conversation_id: uuid.UUID


async def chat_with_persistence(
    session: AsyncSession,
    user: User,
    message: str,
    model: str | None,
    deepseek_service: DeepSeekService | None = None,
) -> ChatResult:
    """
    Persist a user message, call DeepSeek, then persist the assistant reply.

    The user message is committed before the DeepSeek call so a failed upstream
    request never loses the user's input; the assistant reply is only committed
    after a successful response.
    """

    conversation_id = uuid.uuid4()

    user_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role="user",
        content=message,
    )
    session.add(user_message)
    await session.commit()

    if deepseek_service is None:
        deepseek_service = get_deepseek_service()

    resolved_model = model or deepseek_service.default_model
    reply = await deepseek_service.chat(message=message, model=model)

    assistant_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role="assistant",
        content=reply,
        model=resolved_model,
    )
    session.add(assistant_message)
    await session.commit()

    return ChatResult(reply=reply, conversation_id=conversation_id)
