import logging
from datetime import datetime, timedelta
from typing import Any, List
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, extract, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_active_user, get_current_verified_user
from app.api.responses import default_error_responses
from app.core.security import get_password_hash, verify_password
from app.db.models.models import Transaction, User, VerificationCode
from app.db.session import get_db
from app.schemas.schemas import UserMonthlyStats

logger = logging.getLogger(__name__)

router = APIRouter()


# Request schemas for profile operations
class PhoneUpdateRequest(BaseModel):
    """Schema for phone number update request."""

    phone: str = Field(..., min_length=1)


class PasswordUpdateRequest(BaseModel):
    """Schema for password update request."""

    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)


@router.put(
    "/phone",
    summary="Update Phone Number",
    responses=default_error_responses,
)
async def update_phone(
    phone_data: PhoneUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update user's phone number."""
    logger.info(f"Updating phone for user ID: {current_user.id}")

    # Normalize phone number - remove empty strings
    new_phone = phone_data.phone.strip() if phone_data.phone else None

    if not new_phone:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Phone number cannot be empty.",
                "errors": [{"field": "phone", "message": "Phone number is required"}],
            },
        )

    # Check if phone number is already in use by another user
    query = select(User).where(User.phone == new_phone, User.id != current_user.id)
    result = await db.execute(query)
    existing_user = result.scalars().first()

    if existing_user:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "This phone number is already in use. Please try a different one.",
                "errors": [{"field": "phone", "message": "Phone number already exists"}],
            },
        )

    # Determine verification status logic
    # If user was verified via phone and changing phone, they become unverified
    # If user was verified via email, they remain verified
    was_verified_by_phone = current_user.is_verified and current_user.email is None
    new_verification_status = False if was_verified_by_phone else current_user.is_verified

    # Update user's phone number
    current_user.phone = new_phone  # type: ignore
    current_user.is_verified = new_verification_status  # type: ignore
    current_user.updated_at = datetime.utcnow()  # type: ignore

    await db.commit()

    # Create verification code for the new phone number
    await create_verification_code(db, str(current_user.id), "phone")

    logger.info(f"Phone updated successfully for user ID: {current_user.id}")

    return {
        "success": True,
        "message": "Phone number updated successfully. A verification code has been sent to your phone.",
        "is_verified": new_verification_status,
    }


@router.put(
    "/password",
    summary="Update Password",
    responses=default_error_responses,
)
async def update_password(
    password_data: PasswordUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update user's password."""
    logger.info(f"Updating password for user ID: {current_user.id}")

    # Verify current password
    if not verify_password(password_data.currentPassword, str(current_user.hashed_password)):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Current password is incorrect. Please try again.",
                "errors": [{"field": "currentPassword", "message": "Invalid current password"}],
            },
        )

    # Hash new password
    new_hashed_password = get_password_hash(password_data.newPassword)

    # Update user's password
    current_user.hashed_password = new_hashed_password  # type: ignore
    current_user.updated_at = datetime.utcnow()  # type: ignore

    await db.commit()

    logger.info(f"Password updated successfully for user ID: {current_user.id}")

    return {"success": True, "message": "Password changed successfully"}


async def create_verification_code(db: AsyncSession, user_id: str, verification_type: str) -> VerificationCode:
    """Create a verification code."""
    import random
    import string

    # Generate a random 6-digit code
    code = "".join(random.choices(string.digits, k=6))

    # Set expiration time (1 hour)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    verification_id = str(uuid4())

    # Create verification code
    db_verification_code = VerificationCode(
        id=verification_id,
        user_id=user_id,
        code=code,
        type=verification_type,
        expires_at=expires_at,
        is_used=False,
    )

    db.add(db_verification_code)
    await db.commit()
    await db.refresh(db_verification_code)

    return db_verification_code


MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


@router.get(
    "/monthly-summary",
    response_model=List[UserMonthlyStats],
    summary="Get monthly transaction summary for current user",
)
async def get_monthly_transaction_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> List[UserMonthlyStats]:
    """
    Get monthly transaction summary showing received, sent, and revenue for current year.

    Returns:
    - received: Money received (deposits + transfers received + withdrawals in your current logic)
    - sent: Money sent (transfers sent)
    - revenue: received - sent
    """
    current_year = datetime.now().year

    # Build the query with conditional aggregation
    query = (
        select(
            extract("month", Transaction.created_at).label("month"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Transaction.recipient_id == str(current_user.id)) & (Transaction.type == "transfer"),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("received"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Transaction.sender_id == str(current_user.id)) & (Transaction.type == "transfer"),
                            Transaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("sent"),
        )
        .where(
            # User is involved in transaction (either sender or recipient)
            (Transaction.sender_id == str(current_user.id))
            | (Transaction.recipient_id == str(current_user.id))
        )
        .where(extract("year", Transaction.created_at) == current_year)
        .group_by(extract("month", Transaction.created_at))
        .order_by(extract("month", Transaction.created_at))
    )

    result = await db.execute(query)
    db_results = result.all()

    # Create a dictionary from database results
    monthly_data = {}
    for row in db_results:
        month_num = int(row.month)
        received = float(row.received)
        sent = float(row.sent)
        revenue = received - sent

        monthly_data[month_num] = UserMonthlyStats(
            name=MONTH_NAMES[month_num], received=received, sent=sent, revenue=revenue
        )

    # Generate data from January to current month only
    current_month = datetime.now().month
    complete_data = []

    for month_num in range(1, current_month + 1):
        if month_num in monthly_data:
            complete_data.append(monthly_data[month_num])
        else:
            complete_data.append(UserMonthlyStats(name=MONTH_NAMES[month_num], received=0.0, sent=0.0, revenue=0.0))

    return complete_data
