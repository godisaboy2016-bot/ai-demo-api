import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    HistoryResponse,
)
from app.services.chat_service import chat_with_persistence
from app.services.deepseek import (
    DeepSeekService,
    get_deepseek_service,
)
from app.services.history_service import get_chat_history

router = APIRouter(tags=["chat"])

CurrentUser = Annotated[User, Depends(get_current_user)]

ServiceDep = Annotated[
    DeepSeekService,
    Depends(get_deepseek_service),
]

SessionDep = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/api/chat/history",
    response_model=HistoryResponse,
    summary="Get chat history",
)
async def get_history(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Max messages to return"),
    ] = 20,
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor for the next page"),
    ] = None,
    conversation_id: Annotated[
        uuid.UUID | None,
        Query(description="Filter messages by conversation"),
    ] = None,
) -> HistoryResponse:
    """Return the authenticated user's chat messages, newest first."""

    try:
        page = await get_chat_history(
            session=session,
            user_id=current_user.id,
            limit=limit,
            cursor=cursor,
            conversation_id=conversation_id,
        )
    except ValueError:
        raise RequestValidationError(
            errors=[
                {
                    "loc": ("query", "cursor"),
                    "msg": "Invalid cursor",
                    "type": "value_error",
                }
            ]
        ) from None

    return HistoryResponse(
        items=[
            ChatMessageResponse.model_validate(message) for message in page.items
        ],
        next_cursor=page.next_cursor,
    )


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
        conversation_id=payload.conversation_id,
        deepseek_service=service,
    )

    return ChatResponse(
        reply=result.reply,
        conversation_id=result.conversation_id,
    )
