import logging
from typing import Any, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_active_user
from app.api.utils import is_valid_card
from app.db.models.models import PaymentCard, User
from app.db.session import get_db
from app.schemas.schemas import MessageResponse, PaymentCardCreate, PaymentCardResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[PaymentCardResponse])
async def get_all_cards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Fetch the list of payment cards linked to the user."""
    logger.info(f"Getting all payment cards for user ID: {current_user.id}")

    query = (
        select(PaymentCard)
        .where(PaymentCard.user_id == current_user.id, PaymentCard.is_deleted.is_(False))
        .order_by(PaymentCard.is_default.desc(), PaymentCard.created_at.desc())
    )

    result = await db.execute(query)
    cards = result.scalars().all()

    return [
        {
            "id": card.id,
            "name": card.name,
            "cardNumber": card.masked_card_number,
            "expireDate": card.expire_date,
            "cvc": "***",
            "isDefault": card.is_default,
            "type": card.card_type,
            "cardColor": card.card_color,
        }
        for card in cards
    ]


@router.post("/", response_model=dict)
async def add_new_card(
    card_in: PaymentCardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Add a new payment card."""
    logger.info(f"Adding new payment card for user ID: {current_user.id}")

    # Validate card data
    if not card_in.name or not card_in.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card name is required",
        )

    if not card_in.cardNumber or not card_in.cardNumber.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card number is required",
        )

    if not card_in.expireDate or not card_in.expireDate.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expire date is required",
        )

    if not card_in.cvc or not card_in.cvc.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CVC is required",
        )
    card_validation = is_valid_card(card_number=card_in.cardNumber)
    if not card_validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid card number or type does not match",
        )
    # Check if this is the first card (should be default automatically)
    query = select(PaymentCard).where(PaymentCard.user_id == current_user.id, PaymentCard.is_deleted.is_(False))
    result = await db.execute(query)
    existing_cards = result.scalars().all()

    is_first_card = len(existing_cards) == 0
    is_default = card_in.isDefault or is_first_card

    # If setting as default, unset other default cards
    if is_default:
        await _unset_other_default_cards(db, str(current_user.id))

    # Generate unique card ID
    card_id = str(uuid4())

    # Create masked card number (show only last 4 digits)
    masked_number = _mask_card_number(card_in.cardNumber)

    # Create new payment card
    db_card = PaymentCard(
        id=card_id,
        user_id=current_user.id,
        name=card_in.name.strip(),
        card_number_hash=_hash_card_number(card_in.cardNumber),  # Store hashed version
        masked_card_number=masked_number,
        expire_date=card_in.expireDate.strip(),
        cvc_hash=_hash_cvc(card_in.cvc),  # Store hashed version
        is_default=is_default,
        card_type=card_in.type.lower() if card_in.type else _detect_card_type(card_in.cardNumber),
        card_color=card_in.cardColor or "bg-blue-500",
        is_deleted=False,
    )

    db.add(db_card)
    await db.commit()
    await db.refresh(db_card)

    return {"id": card_id, "message": "Card added successfully"}


@router.patch("/{card_id}/default", response_model=MessageResponse)
async def set_card_as_default(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Set a specific card as the default."""
    logger.info(f"Setting card {card_id} as default for user ID: {current_user.id}")

    # Check if card exists and belongs to user
    query = select(PaymentCard).where(
        PaymentCard.id == card_id, PaymentCard.user_id == current_user.id, PaymentCard.is_deleted.is_(False)
    )
    result = await db.execute(query)
    card = result.scalars().first()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    if card.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card is already set as default",
        )

    # Unset other default cards
    await _unset_other_default_cards(db, str(current_user.id))

    # Set this card as default
    card.is_default = True  # type: ignore
    await db.commit()

    return {"message": "Card set as default"}


@router.delete("/{card_id}", response_model=MessageResponse)
async def delete_card(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Delete a card by ID."""
    logger.info(f"Deleting card {card_id} for user ID: {current_user.id}")

    # Check if card exists and belongs to user
    query = select(PaymentCard).where(
        PaymentCard.id == card_id, PaymentCard.user_id == current_user.id, PaymentCard.is_deleted.is_(False)
    )
    result = await db.execute(query)
    card = result.scalars().first()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    # Soft delete the card
    card.is_deleted = True  # type: ignore
    card.is_default = False  # type: ignore

    # If this was the default card, set another card as default
    if card.is_default:
        await _set_next_default_card(db, str(current_user.id))

    await db.commit()

    return {"message": "Card deleted successfully"}


# Helper functions
async def _unset_other_default_cards(db: AsyncSession, user_id: str) -> None:
    """Unset all other default cards for the user."""
    stmt = (
        update(PaymentCard)
        .where(PaymentCard.user_id == user_id, PaymentCard.is_default.is_(True), PaymentCard.is_deleted.is_(False))
        .values(is_default=False)
    )
    await db.execute(stmt)


async def _set_next_default_card(db: AsyncSession, user_id: str) -> None:
    """Set the next available card as default if any exists."""
    query = (
        select(PaymentCard)
        .where(PaymentCard.user_id == user_id, PaymentCard.is_deleted.is_(False))
        .order_by(PaymentCard.created_at.asc())
        .limit(1)
    )

    result = await db.execute(query)
    next_card = result.scalars().first()

    if next_card:
        next_card.is_default = True  # type: ignore


def _mask_card_number(card_number: str) -> str:
    """Mask card number, showing only last 4 digits."""
    # Remove spaces and non-digit characters
    digits_only = "".join(filter(str.isdigit, card_number))

    if len(digits_only) < 4:
        return "**** **** **** ****"

    # Show last 4 digits
    last_four = digits_only[-4:]

    # Determine card type for proper formatting
    if digits_only.startswith("3"):  # Amex
        return f"**** ****** *{last_four}"
    else:  # Visa, Mastercard, etc.
        return f"**** **** **** {last_four}"


def _detect_card_type(card_number: str) -> str:
    """Detect card type from card number."""
    digits_only = "".join(filter(str.isdigit, card_number))

    if digits_only.startswith("4"):
        return "visa"
    elif digits_only.startswith("5"):
        return "mastercard"
    elif digits_only.startswith("3"):
        return "amex"
    elif digits_only.startswith("6"):
        return "discover"
    else:
        return "unknown"


def _hash_card_number(card_number: str) -> str:
    """Hash card number for secure storage."""
    import hashlib

    digits_only = "".join(filter(str.isdigit, card_number))
    return hashlib.sha256(digits_only.encode()).hexdigest()


def _hash_cvc(cvc: str) -> str:
    """Hash CVC for secure storage."""
    import hashlib

    return hashlib.sha256(cvc.encode()).hexdigest()
