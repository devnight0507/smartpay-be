from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, validator


# User schemas
class UserBase(BaseModel):
    """Base user schema."""

    fullname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    is_verified: bool = False

    @validator("phone")
    def phone_must_be_valid(cls, v: Optional[str]) -> str | None:
        """Validate phone number format."""
        if v is None:
            return v
        # Simple validation - in real app would be more robust
        if not v.isdigit() or len(v) < 8:
            raise ValueError("Phone number must contain only digits and be at least 8 digits")
        return v

    @validator("email", "phone")
    def email_or_phone_required(cls, v: Optional[str], values: Any) -> str | None:
        """Validate that either email or phone is provided."""
        if not v and not values.get("email") and not values.get("phone"):
            raise ValueError("Either email or phone must be provided")
        return v


class UserCreate(UserBase):
    """Schema for user creation."""

    password: str = Field(..., min_length=8)


class UserUpdate(UserBase):
    """Schema for user update."""

    password: Optional[str] = Field(None, min_length=8)


class UserInDBBase(UserBase):
    """Base schema for user in DB."""

    id: int
    created_at: datetime
    updated_at: datetime
    verify_code: str

    class Config:
        """Pydantic config."""

        orm_mode = True


class User(UserInDBBase):
    """User schema for responses."""

    pass


class Token(BaseModel):
    """Token schema."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token payload schema."""

    sub: Optional[int] = None


# Wallet schemas
class WalletBase(BaseModel):
    """Base wallet schema."""

    balance: float = 0.0


class WalletCreate(WalletBase):
    """Schema for wallet creation."""

    user_id: int


class WalletUpdate(WalletBase):
    """Schema for wallet update."""

    pass


class WalletInDBBase(WalletBase):
    """Base schema for wallet in DB."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        orm_mode = True


class Wallet(WalletInDBBase):
    """Wallet schema for responses."""

    pass


# Transaction schemas
class TransactionBase(BaseModel):
    """Base transaction schema."""

    amount: float = Field(..., gt=0)
    description: Optional[str] = None
    type: str = "transfer"  # "transfer", "deposit", "withdrawal"


class TransactionCreate(TransactionBase):
    """Schema for transaction creation."""

    recipient_identifier: str  # email or phone number

    @validator("amount")
    def amount_must_be_positive(cls, v: int) -> int:
        """Validate that amount is positive."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class TopUpCreate(BaseModel):
    """Schema for deposit/top-up creation."""

    amount: float = Field(..., gt=0)


class TransactionInDBBase(TransactionBase):
    """Base schema for transaction in DB."""

    id: int
    sender_id: Optional[int] = None
    recipient_id: Optional[int] = None
    status: str = "completed"  # "pending", "completed", "failed"
    created_at: datetime

    class Config:
        """Pydantic config."""

        orm_mode = True


class Transaction(TransactionInDBBase):
    """Transaction schema for responses."""

    pass


# Verification code schemas
class VerificationRequest(BaseModel):
    """Schema for verification request."""

    code: str


class VerificationResponse(BaseModel):
    """Schema for verification response."""

    message: str
    is_verified: bool
