import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_active_user
from app.core.security import get_password_hash, verify_password
from app.db.models.models import User, VerificationCode
from app.db.session import get_db

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

    # In a real application, you would send the code via email or SMS here
    print(f"Verification code for user {user_id}: {code}")

    return db_verification_code
