import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage


@dataclass
class HistoryPage:
    """A page of chat messages and the cursor for the next page."""

    items: list[ChatMessage]
    next_cursor: str | None


def encode_cursor(created_at: datetime, message_id: uuid.UUID) -> str:
    """Encode a (created_at, id) pair into an opaque cursor string."""

    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(message_id)},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor string back into a (created_at, id) pair."""

    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        created_at = datetime.fromisoformat(data["created_at"])
        message_id = uuid.UUID(data["id"])
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, binascii.Error):
        raise ValueError("Invalid cursor.") from None
    return created_at, message_id


async def get_chat_history(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
    cursor: str | None = None,
    conversation_id: uuid.UUID | None = None,
) -> HistoryPage:
    """
    Return a user's chat messages, newest first, with cursor pagination.

    Cursor pagination relies on the stable (created_at DESC, id DESC) ordering,
    so pages never skip or repeat messages when new ones arrive between calls.
    """

    stmt = select(ChatMessage).where(ChatMessage.user_id == user_id)

    if conversation_id is not None:
        stmt = stmt.where(ChatMessage.conversation_id == conversation_id)

    if cursor is not None:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                ChatMessage.created_at < cursor_created_at,
                and_(
                    ChatMessage.created_at == cursor_created_at,
                    ChatMessage.id < cursor_id,
                ),
            )
        )

    stmt = stmt.order_by(
        ChatMessage.created_at.desc(),
        ChatMessage.id.desc(),
    ).limit(limit + 1)

    result = await session.scalars(stmt)
    rows = list(result.all())

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = (
        encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    )

    return HistoryPage(items=items, next_cursor=next_cursor)


async def get_recent_messages(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int,
) -> list[ChatMessage]:
    """
    Return the user's most recent messages in a conversation, oldest first.

    The query uses the same stable ordering as pagination (created_at DESC,
    id DESC); the result is reversed so the caller receives chronological order
    suitable for building a chat context.
    """

    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.user_id == user_id,
            ChatMessage.conversation_id == conversation_id,
        )
        .order_by(
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return list(result.all())[::-1]
