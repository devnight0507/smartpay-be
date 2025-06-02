from typing import Any, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_verified_user,
    get_user_by_email,
    get_user_by_phone,
)
from app.db.models.models import Transaction, User, Wallet
from app.db.session import get_db
from app.schemas.schemas import TopUpCreate
from app.schemas.schemas import Transaction as TransactionSchema
from app.schemas.schemas import TransactionCreate, TransactionWithUsers
from app.schemas.schemas import Wallet as WalletSchema
from app.utils.notifier import notify_user

router = APIRouter()


@router.get("/balance", response_model=WalletSchema)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> Any:
    """Get user's wallet balance."""
    query = select(Wallet).where(Wallet.user_id == current_user.id)
    result = await db.execute(query)
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )

    return wallet


@router.post("/deposit", response_model=WalletSchema)
async def top_up_wallet(
    top_up_data: TopUpCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> Any:
    """Top up wallet (simulated)."""
    query = select(Wallet).where(Wallet.user_id == current_user.id)
    result = await db.execute(query)
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )

    # Update wallet balance
    setattr(wallet, "balance", float(wallet.balance) + top_up_data.amount)
    transaction_id = str(uuid4())
    # Create transaction record
    transaction = Transaction(
        id=transaction_id,
        sender_id=None,  # Top-up has no sender (external source)
        recipient_id=current_user.id,
        amount=top_up_data.amount,
        card_id=str(top_up_data.card_id),
        type="deposit",
        status="completed",
    )

    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)

    return wallet


@router.post("/transfer", response_model=TransactionSchema)
async def transfer_money(
    transaction_data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> Any:
    """Transfer money to another user."""
    # Get sender's wallet
    query = select(Wallet).where(Wallet.user_id == current_user.id)
    result = await db.execute(query)
    sender_wallet = result.scalars().first()

    if not sender_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender wallet not found",
        )

    # Check if sender has enough balance
    if sender_wallet.balance < transaction_data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )

    # Find recipient by email or phone
    recipient = None
    identifier = transaction_data.recipient_identifier

    # Try to find by email
    if "@" in identifier:
        recipient = await get_user_by_email(db, identifier)
    else:
        # Try to find by phone
        recipient = await get_user_by_phone(db, identifier)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found",
        )

    # Get recipient's wallet
    query = select(Wallet).where(Wallet.user_id == recipient.id)
    result = await db.execute(query)
    recipient_wallet = result.scalars().first()

    if not recipient_wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient wallet not found",
        )

    # Update wallets
    setattr(sender_wallet, "balance", float(sender_wallet.balance) - transaction_data.amount)
    setattr(recipient_wallet, "balance", float(recipient_wallet.balance) + transaction_data.amount)

    transaction_id = str(uuid4())
    # Create transaction record
    transaction = Transaction(
        id=transaction_id,
        sender_id=current_user.id,
        recipient_id=recipient.id,
        amount=transaction_data.amount,
        description=transaction_data.description,
        type="transfer",
        status="completed",
    )

    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    print("DEBUG", transaction_id)

    # Notify sender
    await notify_user(
        db=db,
        user_id=str(current_user.id),
        title="Transfer Successful",
        message=(
            f"You sent ${transaction_data.amount:.2f} to "
            f"{recipient.fullname or recipient.email or recipient.phone}"
        ),
        type="transaction",
        transaction_id=str(transaction.id),
        amount=transaction_data.amount,
    )

    await notify_user(
        db=db,
        user_id=str(recipient.id),
        title="You've Received Money",
        message=(
            f"You received ${transaction_data.amount:.2f} from "
            f"{current_user.fullname or current_user.email or current_user.phone}"
        ),
        type="transaction",
        transaction_id=str(transaction.id),
        amount=transaction_data.amount,
    )

    return transaction


@router.post("/withdraw", response_model=WalletSchema, summary="Withdraw Money")
async def withdraw_wallet(
    withdraw: TopUpCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> Any:
    """Withdraw (simulated)."""
    if withdraw.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive",
        )

    query = select(Wallet).where(Wallet.user_id == current_user.id)
    result = await db.execute(query)
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    if wallet.balance < withdraw.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )
    # Update wallet balance
    setattr(wallet, "balance", float(wallet.balance) - withdraw.amount)
    transaction_id = str(uuid4())
    # Create transaction record
    transaction = Transaction(
        id=transaction_id,
        sender_id=None,  # Top-up has no sender (external source)
        recipient_id=current_user.id,
        amount=withdraw.amount,
        card_id=str(withdraw.card_id),
        type="withdraw",
        status="completed",
    )

    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)

    return wallet


@router.get("/transactions", response_model=List[TransactionWithUsers])
async def get_transactions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> Any:
    """Get user's transactions with populated sender and recipient data."""

    query = (
        select(Transaction)
        .where((Transaction.sender_id == current_user.id) | (Transaction.recipient_id == current_user.id))
        .order_by(desc(Transaction.created_at))
        .offset(offset)
        .limit(limit)
        .options(
            # Auto-fetch sender and recipient user objects
            selectinload(Transaction.sender),
            selectinload(Transaction.recipient),
        )
    )

    result = await db.execute(query)
    transactions = result.scalars().all()

    return transactions
