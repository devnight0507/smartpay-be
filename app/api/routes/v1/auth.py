import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import (
    authenticate_user,
    check_rate_limit,
    get_current_active_user,
)
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.models.models import User, VerificationCode, Wallet
from app.db.session import get_db
from app.schemas.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordReset,
    ForgotPasswordResponse,
    ForgotPasswordVerifyCode,
    NotifSettingUpdate,
    Token,
)
from app.schemas.schemas import User as UserSchema
from app.schemas.schemas import UserCreate, VerificationRequest, VerificationResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserSchema,
    summary="Register a new user.",
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register a new user."""
    logger.warning("register!!")

    # Convert empty strings to None for proper NULL handling
    email = user_in.email if user_in.email and user_in.email.strip() else None
    phone = user_in.phone if user_in.phone and user_in.phone.strip() else None

    # Validate that at least one of email or phone is provided
    if not email and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone must be provided",
        )

    # Check if user with email already exists (only if email is provided)
    if email:
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        user_by_email = result.scalars().first()
        if user_by_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )

    # Check if user with phone already exists (only if phone is provided)
    if phone:
        query = select(User).where(User.phone == phone)
        result = await db.execute(query)
        user_by_phone = result.scalars().first()
        if user_by_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone already exists",
            )
    user_id = str(uuid4())
    # Create new user with proper None values
    db_user = User(
        id=user_id,
        fullname=user_in.fullname,
        email=email,  # Will be None if not provided
        phone=phone,  # Will be None if not provided
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_admin=False,
        is_verified=False,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    wallet_id = str(uuid4())
    # Create wallet for user
    db_wallet = Wallet(id=wallet_id, user_id=db_user.id, balance=0.0)
    db.add(db_wallet)
    await db.commit()

    # Create verification code based on what's available
    verification = None
    if email:
        verification = await create_verification_code(db, str(db_user.id), "email")
    elif phone:
        verification = await create_verification_code(db, str(db_user.id), "phone")

    return {
        "id": db_user.id,
        "fullname": db_user.fullname,
        "email": db_user.email,
        "phone": db_user.phone,
        "is_active": db_user.is_active,
        "is_admin": db_user.is_admin,
        "is_verified": db_user.is_verified,
        "verify_code": verification.code if verification else None,
        "created_at": db_user.created_at,
        "updated_at": db_user.updated_at,
    }


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get access token.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Login and get access token."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/me",
    summary="Get authenticated user information",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current authenticated user information."""
    logger.info(f"Getting user info for user ID: {current_user.id}")

    return {
        "id": current_user.id,
        "email": current_user.email,
        "phone": current_user.phone,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
    }


@router.get(
    "/notif-setting",
    summary="Get notif",
)
async def get_notif_setting(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get current authenticated user information."""
    logger.info(f"Getting user info for user ID: {current_user.id}")

    return {
        "notif_setting": current_user.notif_setting,
    }


@router.put(
    "/notif-setting",
    summary="Update notification setting",
)
async def update_notif_setting(
    setting_data: NotifSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    current_user.notif_setting = setting_data.notif_setting  # type: ignore
    await db.commit()
    await db.refresh(current_user)
    return {
        "message": "Notification setting updated successfully",
        "notif_setting": current_user.notif_setting,
    }


@router.post("/verify/{verification_type}", response_model=VerificationResponse)
async def verify_user(
    verification_type: str,
    verification_data: VerificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Verify user with code sent via email or phone."""
    if verification_type not in ["email", "phone"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification type",
        )

    if verification_type == "email" and not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an email",
        )

    if verification_type == "phone" and not current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a phone",
        )

    # Get the latest verification code
    query = (
        select(VerificationCode)
        .where(
            VerificationCode.user_id == current_user.id,
            VerificationCode.type == verification_type,
            VerificationCode.is_used.is_(False),
            VerificationCode.expires_at > datetime.utcnow(),
        )
        .order_by(VerificationCode.created_at.desc())
    )

    result = await db.execute(query)
    verification_code = result.scalars().first()

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid verification code found",
        )

    if verification_code.code != verification_data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    # Mark code as used
    verification_code.is_used = True  # type: ignore

    # Mark user as verified
    current_user.is_verified = True  # type: ignore

    await db.commit()

    return {
        "message": f"User verified via {verification_type}",
        "is_verified": True,
    }


@router.post("/resend-verification/{verification_type}", response_model=dict)
async def resend_verification(
    verification_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Resend verification code."""
    if verification_type not in ["email", "phone"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification type",
        )

    if verification_type == "email" and not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an email",
        )

    if verification_type == "phone" and not current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a phone",
        )

    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already verified",
        )

    verification = await create_verification_code(db, str(current_user.id), verification_type)

    return {"message": f"Verification code sent via {verification_type}", "verification_code": verification.code}


async def create_verification_code(db: AsyncSession, user_id: str, verification_type: str) -> VerificationCode:
    """
    Create a verification code.

    Args:
        db: Database session
        user_id: User ID
        verification_type: Type of verification ("email", "phone", "password_reset")
    """
    import random
    import string

    # Generate a random 6-digit code
    code = "".join(random.choices(string.digits, k=6))

    # Set expiration time based on type
    if verification_type == "password_reset":
        expires_at = datetime.utcnow() + timedelta(minutes=15)  # Shorter expiry for security
    else:
        expires_at = datetime.utcnow() + timedelta(hours=1)  # Default 1 hour

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
    logger.info(f"Verification code created for user {user_id} ({verification_type}): {code}")

    return db_verification_code


@router.get(
    "/{username}",
    summary="Get User by user email or phone",
)
async def get_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get User by user email or phone"""

    query = select(User).where(or_(User.email == username, User.phone == username))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "Not Found",
                    "message": f"User Not Found : {username}",
                }
            },
        )
    elif user.is_verified is False:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "Permission Denied.",
                    "message": f"User Not Verified : {username}",
                }
            },
        )
    else:
        return {
            "id": user.id,
            "fullname": user.fullname,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }


@router.post(
    "/forgot-password/send-code",
    response_model=ForgotPasswordResponse,
    summary="Step 1: Send password reset verification code",
)
async def send_password_reset_code(
    request_data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Step 1: Send password reset verification code to user's email.

    Rate Limited: 3 attempts per hour per email address.
    """
    # Apply rate limiting
    await check_rate_limit(
        request=request,
        db=db,
        email=request_data.email,
        endpoint="forgot_password_send_code",
        max_attempts=3,
        window_minutes=60,
    )

    # Check if user exists
    query = select(User).where(User.email == request_data.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        # For security, don't reveal if email exists or not
        return ForgotPasswordResponse(
            success=True,
            message="If this email exists, you will receive a password reset code",
            verified_code="",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated. Contact support.")

    # Create password reset verification code
    verification = await create_verification_code(db, str(user.id), "password_reset")

    # In production, send email here
    # await send_password_reset_email(user.email, verification.code)
    logger.info(f"Password reset code for {request_data.email}: {verification.code}")

    return ForgotPasswordResponse(
        success=True, message="Password reset code sent to your email", verified_code=str(verification.code)
    )


@router.post(
    "/forgot-password/verify-code",
    response_model=ForgotPasswordResponse,
    summary="Step 2: Verify password reset code",
)
async def verify_password_reset_code(
    verify_data: ForgotPasswordVerifyCode,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Step 2: Verify the password reset code.

    Rate Limited: 5 attempts per 30 minutes per email address.
    """
    # Apply rate limiting
    await check_rate_limit(
        request=request,
        db=db,
        email=verify_data.email,
        endpoint="forgot_password_verify_code",
        max_attempts=5,
        window_minutes=30,
    )

    # Check if user exists
    query = select(User).where(User.email == verify_data.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get the latest verification code for password reset
    query = (
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.type == "password_reset",
            VerificationCode.is_used.is_(False),
            VerificationCode.expires_at > datetime.utcnow(),
        )
        .order_by(VerificationCode.created_at.desc())
    )

    result = await db.execute(query)
    verification_code = result.scalars().first()

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No valid verification code found or code has expired"
        )

    if verification_code.code != verify_data.verify_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    return ForgotPasswordResponse(
        success=True, message="Verification code is valid", verified_code=verify_data.verify_code
    )


@router.post(
    "/forgot-password/reset-password",
    response_model=ForgotPasswordResponse,
    summary="Step 3: Reset password with verified code",
)
async def reset_password_with_code(
    reset_data: ForgotPasswordReset,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Step 3: Reset password using verified code.

    Rate Limited: 3 attempts per hour per email address.
    """
    # Apply rate limiting
    await check_rate_limit(
        request=request,
        db=db,
        email=reset_data.email,
        endpoint="forgot_password_reset",
        max_attempts=6,
        window_minutes=60,
    )

    # Check if user exists
    query = select(User).where(User.email == reset_data.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get and verify the code again (security best practice)
    query = (
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.type == "password_reset",
            VerificationCode.is_used.is_(False),
            VerificationCode.expires_at > datetime.utcnow(),
        )
        .order_by(VerificationCode.created_at.desc())
    )

    result = await db.execute(query)
    verification_code = result.scalars().first()

    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No valid verification code found or code has expired"
        )

    if verification_code.code != reset_data.verify_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    # Update user's password
    user.hashed_password = get_password_hash(reset_data.new_password)  # type: ignore

    # Mark verification code as used
    verification_code.is_used = True  # type: ignore

    await db.commit()

    return ForgotPasswordResponse(
        success=True, message="Password has been reset successfully", verified_code=reset_data.verify_code
    )
