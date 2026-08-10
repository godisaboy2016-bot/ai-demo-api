from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the profile of the currently authenticated user."""

    return UserResponse.model_validate(current_user)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: RegisterRequest,
    session: SessionDep,
) -> UserResponse:
    """Create a new user account and return its public profile."""

    user = await register_user(
        session=session,
        email=payload.email,
        password=payload.password,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and get an access token",
)
async def login(
    payload: LoginRequest,
    session: SessionDep,
) -> TokenResponse:
    """Validate credentials and return a JWT access token."""

    user = await authenticate_user(
        session=session,
        email=payload.email,
        password=payload.password,
    )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)
