import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import (
    authenticate_user,
    check_rate_limit,
    get_current_active_user,
)
from app.api.responses import default_error_responses
from app.api.utils import is_valid_email_dns
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
)
from app.db.models.models import User, VerificationCode, Wallet
from app.db.session import get_db
from app.schemas.schemas import (
    AccessTokenOnly,
    ForgotPasswordRequest,
    ForgotPasswordReset,
    ForgotPasswordResponse,
    ForgotPasswordVerifyCode,
    NotifSettingUpdate,
    RefreshRequest,
    Token,
)
from app.schemas.schemas import User as UserSchema
from app.schemas.schemas import UserCreate, VerificationRequest, VerificationResponse
from app.utils.resend_mailer import send_verification_code

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"

raw_key = os.getenv("ENCRYPTION_KEY")

# Generate a valid Fernet key if missing or invalid
if not raw_key or len(raw_key.encode()) != 44:
    raw_key = Fernet.generate_key().decode()

assert raw_key is not None
ENCRYPTION_KEY = raw_key.encode()

fernet = Fernet(ENCRYPTION_KEY)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserSchema,
    summary="Register a new user.",
    responses=default_error_responses,
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register a new user."""
    logger.info("Hello file logs!")

    # Convert empty strings to None for proper NULL handling
    email = user_in.email if user_in.email and user_in.email.strip() else None
    phone = user_in.phone if user_in.phone and user_in.phone.strip() else None

    # Validate that at least one of email or phone is provided
    if not email and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone must be provided",
        )
    if email:
        if not is_valid_email_dns(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format",
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
        await send_verification_code(str(db_user.email), str(verification.code))

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
        "created_at": db_user.created_at,
        "updated_at": db_user.updated_at,
    }


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get access token.",
    responses=default_error_responses,
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
    refresh_token_expires = timedelta(days=1)  # or from settings.REFRESH_TOKEN_EXPIRE_DAYS

    access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(subject=user.id, expires_delta=refresh_token_expires)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
    }


@router.post("/refresh-token", response_model=AccessTokenOnly)
async def refresh_token(data: RefreshRequest) -> dict:
    token = data.refresh_token

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access_token = create_access_token(subject=payload["sub"], expires_delta=timedelta(minutes=15))
    return {"access_token": new_access_token, "token_type": "bearer"}


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


@router.post(
    "/verify/{verification_type}",
    response_model=VerificationResponse,
    responses=default_error_responses,
)
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


@router.post(
    "/resend-verification/{verification_type}",
    response_model=dict,
    responses=default_error_responses,
)
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
    await send_verification_code(str(current_user.email), str(verification.code))

    return {"message": f"Verification code sent via {verification_type}"}


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
        expires_at = datetime.utcnow() + timedelta(minutes=1)  # Shorter expiry for security
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
    responses=default_error_responses,
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
    responses=default_error_responses,
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
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated. Contact support.")

    # Create password reset verification code
    verification = await create_verification_code(db, str(user.id), "password_reset")
    await send_verification_code(str(request_data.email), str(verification.code))
    # In production, send email here
    # await send_password_reset_email(user.email, verification.code)
    logger.info(f"Password reset code for {request_data.email}: {verification.code}")

    return ForgotPasswordResponse(success=True, message="Password reset code sent to your email")


@router.post(
    "/forgot-password/verify-code",
    response_model=ForgotPasswordResponse,
    summary="Step 2: Verify password reset code and get token",
    responses=default_error_responses,
)
async def verify_password_reset_code(
    verify_data: ForgotPasswordVerifyCode,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    # ============ UTILITY FUNCTIONS INSIDE THIS FUNCTION ============
    def encrypt_email(email: str) -> str:
        """Encrypt email address"""
        return str(fernet.encrypt(email.encode()).decode())

    def create_reset_token(email: str, expires_delta: timedelta = timedelta(minutes=1)) -> str:
        """Create JWT token with encrypted email"""
        encrypted_email = encrypt_email(email)
        expire = datetime.utcnow() + expires_delta
        to_encode = {
            "encrypted_email": encrypted_email,
            "exp": expire,
            "type": "password_reset",
            "iat": datetime.utcnow(),
        }
        return str(jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM))

    # ================================================================

    try:
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

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated. Contact support."
            )

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

        # Create JWT token with encrypted email (15 minutes expiry)
        reset_token = create_reset_token(user.email, expires_delta=timedelta(minutes=15))  # type: ignore

        return ForgotPasswordResponse(
            success=True,
            message="Verification code is valid. Use the token to reset your password.",
            token=reset_token,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_password_reset_code: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Debug Info: {str(e)}")


# ====================================================================
# FUNCTION 2: RESET PASSWORD WITH JWT TOKEN
# ====================================================================


@router.post(
    "/forgot-password/reset-password",
    response_model=ForgotPasswordResponse,
    summary="Step 3: Reset password with JWT token",
)
async def reset_password_with_code(
    reset_data: ForgotPasswordReset,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Step 3: Reset password using JWT token.
    Rate Limited: 6 attempts per hour per email address.
    """

    # ============ UTILITY FUNCTIONS INSIDE THIS FUNCTION ============
    def decrypt_email(encrypted_email: str) -> str:
        """Decrypt email address"""
        return str(fernet.decrypt(encrypted_email.encode()).decode())

    def verify_reset_token(token: str) -> Optional[str]:
        """Verify JWT token and return decrypted email"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            encrypted_email: str = payload.get("encrypted_email")
            token_type: str = payload.get("type")

            if encrypted_email is None or token_type != "password_reset":
                return None

            # Decrypt email
            email = decrypt_email(encrypted_email)
            return email

        except JWTError:
            return None
        except Exception:  # Decryption error
            return None

    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Validate password strength and return (is_valid, error_message)"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        return True, ""

    # ================================================================

    try:
        # 1. Verify and decode the JWT token to get user's email
        email = verify_reset_token(reset_data.token)
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

        # 2. Apply rate limiting using the decoded email
        await check_rate_limit(
            request=request,
            db=db,
            email=email,
            endpoint="forgot_password_reset",
            max_attempts=6,
            window_minutes=60,
        )

        # 3. Find user by the decrypted email
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated. Contact support."
            )

        # 4. Validate that there's still a valid verification code
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

        # 5. Validate new password strength
        is_valid, error_msg = validate_password_strength(reset_data.newpassword)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        # 6. Update user's password
        user.hashed_password = get_password_hash(reset_data.newpassword)  # type: ignore

        # 8. Commit all changes to database
        await db.commit()

        logger.info(f"Password successfully reset for user: {email}")

        return ForgotPasswordResponse(success=True, message="Password has been reset successfully", token=None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset_password_with_code: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while resetting the password"
        )
