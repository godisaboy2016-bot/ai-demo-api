from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request payload for the chat endpoint."""

    message: str = Field(..., min_length=1, max_length=4096, description="User message")
    model: str | None = Field(default=None, description="Optional DeepSeek model override")


class ChatResponse(BaseModel):
    """Response payload from the chat endpoint."""

    reply: str
