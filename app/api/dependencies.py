"""
FastAPI API dependencies.
"""

from typing import Any, AsyncGenerator, Callable, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory


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

def get_current_user() -> Callable:
    """
    Dependency for getting the current authenticated user.
    """

    async def _get_current_user(request: Request) -> Dict:
        # Authentication logic here (e.g., JWT validation)
        authorization: Optional[str] = request.headers.get("Authorization")

        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        # Simple example - in reality, you would validate tokens properly
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        # Mock user for demonstration purposes
        return {
            "id": "user_123",
            "email": "user@example.com",
            "roles": ["user"],
        }

    return _get_current_user


def require_roles(roles: list[str]) -> Callable:
    """
    Dependency for role-based access control.
    """

    async def _require_roles(current_user: Dict = Depends(get_current_user())) -> Dict:
        user_roles = current_user.get("roles", [])

        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return _require_roles
