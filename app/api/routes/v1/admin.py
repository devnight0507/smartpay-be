from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

# from sqlalchemy import desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_admin
from app.db.models.models import User, Wallet
from app.db.session import get_db

# from app.schemas.schemas import Transaction as TransactionSchema
from app.schemas.schemas import User as UserSchema
from app.schemas.schemas import UserActiveRequest, UserActiveResponseUpdate

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
    "/user/{user_id}/activate",
    response_model=UserActiveRequest,
    summary="Admin can active/inactive the specific users",
)
async def toggle_user_active(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> UserActiveResponseUpdate:
    """Toggle user verification status."""
    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        elif user.is_active:
            user.is_active = False  # type: ignore
        else:
            user.is_active = True  # type: ignore

    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error")
    return UserActiveResponseUpdate(success=True)


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


# @router.get("/transactions", response_model=List[TransactionSchema])
# async def get_all_transactions(
#     limit: int = 100,
#     offset: int = 0,
#     db: AsyncSession = Depends(get_db),
#     _: User = Depends(get_current_admin),  # Check if user is admin
# ) -> Any:
#     """Get list of all transactions."""
#     query = select(Transaction).order_by(desc(Transaction.created_at)).offset(offset).limit(limit)

#     result = await db.execute(query)
#     transactions = result.scalars().all()

#     return transactions


# @router.get("/stats", response_model=dict)
# async def get_stats(
#     db: AsyncSession = Depends(get_db),
#     _: User = Depends(get_current_admin),  # Check if user is admin
# ) -> Any:
#     """Get system statistics."""
#     # Total users
#     users_query = select(func.count()).select_from(User)
#     result = await db.execute(users_query)
#     total_users = result.scalar()

#     # Verified users
#     verified_users_query = select(func.count()).select_from(User).where(User.is_verified.is_(True))
#     result = await db.execute(verified_users_query)
#     verified_users = result.scalar()

#     # Total transactions
#     transactions_count_query = select(func.count()).select_from(Transaction)
#     result = await db.execute(transactions_count_query)
#     total_transactions = result.scalar()

#     # Total transaction volume
#     volume_query = select(func.sum(Transaction.amount)).select_from(Transaction)
#     result = await db.execute(volume_query)
#     total_volume = result.scalar() or 0

#     # Transaction types
#     types_query = select(Transaction.type, func.count()).group_by(Transaction.type).select_from(Transaction)
#     result = await db.execute(types_query)
#     transaction_types = {type_: count for type_, count in result}

#     return UserActiveResponseUpdate(success=True)
