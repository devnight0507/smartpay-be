from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_admin
from app.db.models.models import Transaction, User, Wallet
from app.db.session import get_db
from app.schemas.schemas import Transaction as TransactionSchema
from app.schemas.schemas import User as UserSchema

router = APIRouter()


@router.get("/users", response_model=List[UserSchema])
async def get_users(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get list of all users."""
    query = select(User).offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return users


@router.get("/users/{user_id}", response_model=UserSchema)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get user by ID."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


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


@router.get("/transactions", response_model=List[TransactionSchema])
async def get_all_transactions(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get list of all transactions."""
    query = select(Transaction).order_by(desc(Transaction.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return transactions


@router.get("/stats", response_model=dict)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),  # Check if user is admin
) -> Any:
    """Get system statistics."""
    # Total users
    users_query = select(func.count()).select_from(User)
    result = await db.execute(users_query)
    total_users = result.scalar()

    # Verified users
    verified_users_query = select(func.count()).select_from(User).where(User.is_verified.is_(True))
    result = await db.execute(verified_users_query)
    verified_users = result.scalar()

    # Total transactions
    transactions_count_query = select(func.count()).select_from(Transaction)
    result = await db.execute(transactions_count_query)
    total_transactions = result.scalar()

    # Total transaction volume
    volume_query = select(func.sum(Transaction.amount)).select_from(Transaction)
    result = await db.execute(volume_query)
    total_volume = result.scalar() or 0

    # Transaction types
    types_query = select(Transaction.type, func.count()).group_by(Transaction.type).select_from(Transaction)
    result = await db.execute(types_query)
    transaction_types = {type_: count for type_, count in result}

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "total_transactions": total_transactions,
        "total_volume": total_volume,
        "transaction_types": transaction_types,
    }
