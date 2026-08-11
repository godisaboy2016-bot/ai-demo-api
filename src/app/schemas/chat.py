from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """Request payload for the chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="User message sent to DeepSeek",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="Optional conversation to continue; omitted creates a new one",
    )

    model: str | None = Field(
        default=None,
        description="Optional DeepSeek model override",
    )

    @field_validator("model")
    @classmethod
    def _normalize_model(cls, value: str | None) -> str | None:
        """Treat blank model strings as unspecified so they never reach DeepSeek."""

        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "请介绍一下 FastAPI",
                    "model": "deepseek-chat",
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    """Response payload from the chat endpoint."""

    reply: str = Field(
        ...,
        description="AI generated response",
    )
    conversation_id: UUID = Field(
        ...,
        description="Conversation id shared by the user message and AI reply",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "reply": "FastAPI is a modern Python web framework...",
                    "conversation_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
                }
            ]
        }
    }


class ChatMessageResponse(BaseModel):
    """A single chat message returned by the history endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Message id")
    conversation_id: UUID = Field(
        ...,
        description="Conversation id this message belongs to",
    )
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    model: str | None = Field(
        default=None,
        description="Model used for assistant replies",
    )
    created_at: datetime = Field(..., description="Message creation time")


class HistoryResponse(BaseModel):
    """A page of chat history messages."""

    items: list[ChatMessageResponse] = Field(
        ...,
        description="Chat messages, newest first",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Cursor for the next page, or null when there are no more",
    )
