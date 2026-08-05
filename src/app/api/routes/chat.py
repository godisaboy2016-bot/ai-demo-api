from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.deepseek import DeepSeekError, DeepSeekService, get_deepseek_service

router = APIRouter(tags=["chat"])

ServiceDep = Annotated[DeepSeekService, Depends(get_deepseek_service)]


@router.post("/api/chat", response_model=ChatResponse, summary="Chat with DeepSeek")
async def chat(
    payload: ChatRequest,
    service: ServiceDep,
) -> ChatResponse:
    """Send a user message to the DeepSeek API and return the AI reply."""
    try:
        reply = await service.chat(message=payload.message, model=payload.model)
    except DeepSeekError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ChatResponse(reply=reply)
