"""
FastAPI API dependencies.
"""

from typing import AsyncGenerator, Callable, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
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
