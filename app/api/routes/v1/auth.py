import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import authenticate_user, get_current_active_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.models.models import User, VerificationCode, Wallet
from app.db.session import get_db
from app.schemas.schemas import Token
from app.schemas.schemas import User as UserSchema
from app.schemas.schemas import UserCreate, VerificationRequest, VerificationResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=UserSchema)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Register a new user."""
    logger.warning("register!!")

    if user_in.email:
        query = select(User).where(User.email == user_in.email)
        result = await db.execute(query)
        user_by_email = result.scalars().first()
        if user_by_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )

    # Check if user with phone already exists
    if user_in.phone:
        query = select(User).where(User.phone == user_in.phone)
        result = await db.execute(query)
        user_by_phone = result.scalars().first()
        if user_by_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone already exists",
            )

    # Create new user
    db_user = User(
        fullname=user_in.fullname,
        email=user_in.email,
        phone=user_in.phone,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_admin=False,
        is_verified=False,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Create wallet for user
    db_wallet = Wallet(user_id=db_user.id, balance=0.0)
    db.add(db_wallet)
    await db.commit()

    # Create verification code
    # if user_in.email:
    #     await create_verification_code(db, int(db_user.id), "email")
    # elif user_in.phone:
    #     await create_verification_code(db, int(db_user.id), "phone")

    # return db_user

    if user_in.email:
        verification = await create_verification_code(db, int(db_user.id), "email")
    elif user_in.phone:
        verification = await create_verification_code(db, int(db_user.id), "phone")
    else:
        verification = None

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


@router.post("/login", response_model=Token)
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

    await create_verification_code(db, int(current_user.id), verification_type)

    return {"message": f"Verification code sent via {verification_type}"}


async def create_verification_code(db: AsyncSession, user_id: int, verification_type: str) -> VerificationCode:
    """Create a verification code."""
    import random
    import string

    # Generate a random 6-digit code
    code = "".join(random.choices(string.digits, k=6))

    # Set expiration time (1 hour)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Create verification code
    db_verification_code = VerificationCode(
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
