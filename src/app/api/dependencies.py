from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _invalid_token() -> AuthError:
    """Return the standard 401 error for invalid tokens."""

    return AuthError("Invalid token.", error_code="invalid_token")


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from the bearer token."""

    if credentials is None:
        raise _invalid_token()

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise _invalid_token() from None

    if payload.get("type") != "access":
        raise _invalid_token()

    subject = payload.get("sub")
    if subject is None:
        raise _invalid_token()
    try:
        user_id = UUID(str(subject))
    except ValueError:
        raise _invalid_token() from None

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise _invalid_token()

    return user
