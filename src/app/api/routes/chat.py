from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_with_persistence
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

SessionDep = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Chat with DeepSeek",
)
async def chat(
    payload: ChatRequest,
    session: SessionDep,
    service: ServiceDep,
    current_user: CurrentUser,
) -> ChatResponse:
    """
    Send an authenticated user's message to the DeepSeek API and return the AI reply.
    """

    result = await chat_with_persistence(
        session=session,
        user=current_user,
        message=payload.message,
        model=payload.model,
        deepseek_service=service,
    )

    return ChatResponse(
        reply=result.reply,
        conversation_id=result.conversation_id,
    )
