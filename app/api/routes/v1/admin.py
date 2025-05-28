from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

# from sqlalchemy import desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_admin
from app.core.security import get_password_hash
from app.db.models.models import User, Wallet
from app.db.session import get_db

# from app.schemas.schemas import Transaction as TransactionSchema
from app.schemas.schemas import AdminPasswordUpdateRequest
from app.schemas.schemas import User as UserSchema
from app.schemas.schemas import UserActiveResponseUpdate

router = APIRouter()


@router.get("/users", response_model=List[UserSchema])
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get list of all users."""
    try:
        query = select(User)
        result = await db.execute(query)
        users = result.scalars().all()
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")

    return users


@router.patch(
    "/admin/{user_id}/activate",
    response_model=UserActiveResponseUpdate,
    summary="Admin can activate/deactivate specific users",
)
async def toggle_user_active(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> UserActiveResponseUpdate:
    """Toggle user active status."""
    try:
        # Find the user
        user_id_str = str(user_id)
        query = select(User).where(User.id == user_id_str)
        # query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")

        # Toggle the active status
        old_status = user.is_active
        new_status = not old_status
        user.is_active = bool(new_status)  # type: ignore

        # Commit the changes
        await db.commit()
        await db.refresh(user)

        return UserActiveResponseUpdate(
            success=True,
            message=f"User {'activated' if new_status else 'deactivated'} successfully",
            is_active=new_status,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error in toggle_user_active: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update user status: {str(e)}"
        )


@router.put("/admin/{user_id}/password", summary="Admin updates user's password")
async def update_user_password(
    user_id: UUID,
    payload: AdminPasswordUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    """Admin updates a specific user's password."""
    try:
        result = await db.execute(select(User).where(User.id == str(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.hashed_password = get_password_hash(payload.new_password)  # type: ignore
        await db.commit()
        return {"message": f"Password updated successfully for user {user_id}"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update password: {str(e)}")


@router.get("/wallets", response_model=List[dict])
async def get_wallets(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get list of all wallets with user information."""
    query = (
        select(
            Wallet.id,
            Wallet.user_id,
            Wallet.balance,
            User.email,
            User.phone,
            User.is_verified,
        )
        .join(User, User.id == Wallet.user_id)
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    wallets = [
        {
            "id": row[0],
            "user_id": row[1],
            "balance": row[2],
            "email": row[3],
            "phone": row[4],
            "is_verified": row[5],
        }
        for row in result
    ]

    return wallets
