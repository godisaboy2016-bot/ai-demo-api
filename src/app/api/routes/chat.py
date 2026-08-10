from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.deepseek import (
    DeepSeekService,
    get_deepseek_service,
)

router = APIRouter(tags=["chat"])

CurrentUser = Annotated[User, Depends(get_current_user)]

ServiceDep = Annotated[
    DeepSeekService,
    Depends(get_deepseek_service),
]


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Chat with DeepSeek",
)
async def chat(
    payload: ChatRequest,
    service: ServiceDep,
    current_user: CurrentUser,
) -> ChatResponse:
    """
    Send an authenticated user's message to the DeepSeek API and return the AI reply.
    """

    reply = await service.chat(
        message=payload.message,
        model=payload.model,
    )

    return ChatResponse(reply=reply)
