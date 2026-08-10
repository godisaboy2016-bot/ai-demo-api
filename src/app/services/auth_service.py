from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ConflictError
from app.core.security import hash_password, verify_password
from app.models.user import User


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Create a new user account and return the persisted user."""

    normalized_email = _normalize_email(email)

    existing = await session.scalar(
        select(User).where(User.email == normalized_email)
    )
    if existing is not None:
        raise ConflictError("User with this email already exists.")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Validate credentials and return the matching user."""

    normalized_email = _normalize_email(email)

    user = await session.scalar(
        select(User).where(User.email == normalized_email)
    )
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password.")

    return user
