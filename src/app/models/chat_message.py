import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class ChatMessage(Base):
    """A single message in a user's chat history."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="chat_messages")

    __table_args__ = (
        # 命名约定生成 ck_chat_messages_role
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        Index(
            "ix_chat_messages_user_created_id",
            "user_id",
            created_at.desc(),
            id.desc(),
        ),
        Index(
            "ix_chat_messages_conversation_created_id",
            "conversation_id",
            created_at.desc(),
            id.desc(),
        ),
    )
