from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request payload for the chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="User message sent to DeepSeek",
    )

    model: str | None = Field(
        default=None,
        description="Optional DeepSeek model override",
    )

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
