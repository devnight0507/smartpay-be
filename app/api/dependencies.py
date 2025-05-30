"""
FastAPI API dependencies.
"""

from datetime import datetime, timedelta
from typing import AsyncGenerator, Callable, Dict, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.security import verify_password
from app.db.models.models import User
from app.db.session import async_session_factory, get_db
from app.schemas.schemas import TokenPayload


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting an async database session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get user by email."""
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalars().first()  # type: ignore[no-any-return]


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """Get user by phone."""
    query = select(User).where(User.phone == phone)
    result = await db.execute(query)
    return result.scalars().first()  # type: ignore[no-any-return]


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate user with email/phone and password."""
    # Try with email
    user = await get_user_by_email(db, email=username)
    if not user:
        # Try with phone
        user = await get_user_by_phone(db, phone=username)

    if not user:
        return None

    if not verify_password(password, str(user.hashed_password)):
        return None

    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """Get current user from token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    query = select(User).where(User.id == token_data.sub)
    result = await db.execute(query)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    return user  # type: ignore[no-any-return]


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current verified user."""
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified")
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Get current admin user."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user


def require_roles(roles: list[str]) -> Callable:
    """
    Dependency for role-based access control.
    """

    async def _require_roles(current_user: User = Depends(get_current_user)) -> Dict:
        user_roles = current_user.get("roles", [])

        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return _require_roles


async def check_rate_limit(
    request: Request, db: AsyncSession, email: str, endpoint: str, max_attempts: int = 3, window_minutes: int = 60
) -> None:
    """
    Check if the email has exceeded rate limit for the specific endpoint.

    Args:
        request: FastAPI request object
        db: Database session
        email: Email address to check
        endpoint: Endpoint identifier (e.g., "forgot_password_send_code")
        max_attempts: Maximum attempts allowed (default: 3)
        window_minutes: Time window in minutes (default: 60)

    Raises:
        HTTPException: If rate limit is exceeded
    """
    # Import here to avoid circular imports
    from app.db.models.models import RateLimitLog

    # Calculate the time window
    window_start = datetime.utcnow() - timedelta(minutes=window_minutes)

    # Count recent attempts for this email and endpoint
    query = select(func.count(RateLimitLog.id)).where(
        and_(RateLimitLog.email == email, RateLimitLog.endpoint == endpoint, RateLimitLog.created_at >= window_start)
    )

    result = await db.execute(query)
    attempt_count = result.scalar() or 0  # Handle None case

    if attempt_count >= max_attempts:
        # Calculate time until next attempt is allowed
        query_latest = (
            select(RateLimitLog.created_at)
            .where(
                and_(
                    RateLimitLog.email == email,
                    RateLimitLog.endpoint == endpoint,
                    RateLimitLog.created_at >= window_start,
                )
            )
            .order_by(RateLimitLog.created_at.asc())
            .limit(1)
        )

        result_latest = await db.execute(query_latest)
        oldest_attempt = result_latest.scalar()

        if oldest_attempt:
            time_until_reset = oldest_attempt + timedelta(minutes=window_minutes)
            minutes_remaining = int((time_until_reset - datetime.utcnow()).total_seconds() / 60)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {max(1, minutes_remaining)} minutes.",
            )

    # Log this attempt
    client_ip = request.client.host if request.client else "unknown"

    rate_limit_log = RateLimitLog(
        id=str(uuid4()), email=email, endpoint=endpoint, ip_address=client_ip, created_at=datetime.utcnow()
    )

    db.add(rate_limit_log)
    await db.commit()
