from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, root_validator, validator


# User schemas
class UserBase(BaseModel):
    """Base user schema."""

    fullname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    is_verified: bool = False

    @validator("email", pre=True)
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None for email."""
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @validator("phone", pre=True)
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Convert empty strings to None for phone."""
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @root_validator(skip_on_failure=True)
    def email_or_phone_required(cls, values: dict) -> dict:
        """Validate that either email or phone is provided."""
        email = values.get("email")
        phone = values.get("phone")

        if not email and not phone:
            raise ValueError("Either email or phone must be provided")
        return values


class UserCreate(UserBase):
    """Schema for user creation."""

    password: str = Field(..., min_length=8)


class UserUpdate(UserBase):
    """Schema for user update."""

    password: Optional[str] = Field(None, min_length=8)


class UserInDBBase(UserBase):
    """Base schema for user in DB."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    verify_code: Optional[str] = None

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

    sub: Optional[str] = None


class NotifSettingUpdate(BaseModel):
    notif_setting: str = Field(
        ...,
        description="Notification setting preference",
    )


class NotifSettingResponse(BaseModel):
    notif_setting: str = Field(description="Current notification setting")

    class Config:
        from_attributes = True


class NotifiSettingUpdateResponse(BaseModel):
    message: str = Field(description="Success message")
    notif_setting: str = Field(description="Updated notification setting")

    class Config:
        from_attributes = True


# Wallet schemas
class WalletBase(BaseModel):
    """Base wallet schema."""

    balance: float = 0.0


class SimpleUser(BaseModel):
    """Lightweight user schema for transaction context."""

    id: UUID
    fullname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    class Config:
        orm_mode = True


class SimplePaymentCard(BaseModel):
    """Minimal card data for transaction reference."""

    id: str
    masked_card_number: str
    card_type: str
    card_color: str

    class Config:
        orm_mode = True


class TransactionWithUsers(BaseModel):
    """Transaction schema with sender and recipient data."""

    id: UUID
    sender_id: Optional[UUID] = None
    recipient_id: Optional[UUID] = None
    amount: float
    description: Optional[str] = None
    type: str  # "transfer", "deposit", "withdrawal"
    card_id: Optional[UUID] = None
    status: str = "completed"
    created_at: datetime

    sender: Optional[SimpleUser] = None
    recipient: Optional[SimpleUser] = None
    card: Optional[SimplePaymentCard] = None

    class Config:
        orm_mode = True


class WalletCreate(WalletBase):
    """Schema for wallet creation."""

    user_id: UUID


class WalletUpdate(WalletBase):
    """Schema for wallet update."""

    pass


class WalletInDBBase(WalletBase):
    """Base schema for wallet in DB."""

    id: UUID
    user_id: UUID
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
    def amount_must_be_positive(cls, v: float) -> float:
        """Validate that amount is positive."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class TopUpCreate(BaseModel):
    """Schema for deposit/top-up creation."""

    amount: float = Field(..., gt=0)
    card_id: UUID


class TransactionInDBBase(TransactionBase):
    """Base schema for transaction in DB."""

    id: UUID
    sender_id: Optional[UUID] = None
    recipient_id: Optional[UUID] = None
    type: str  # "deposit", "transtfer", "withdraw", "receive"
    card_id: Optional[UUID] = None
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


# Transaction schemas
class PaymentCardBase(BaseModel):
    """Base payment card schema."""

    name: str = Field(..., min_length=1, max_length=100)
    cardNumber: str = Field(..., min_length=13, max_length=19)
    expireDate: str = Field(..., pattern=r"^(0[1-9]|1[0-2])\/\d{2}$")  # MM/YY format
    cvc: str = Field(..., min_length=3, max_length=4)
    isDefault: bool = False
    type: Optional[str] = None
    cardColor: str = "bg-blue-500"

    @validator("name", pre=True)
    def normalize_name(cls, v: str) -> str:
        """Normalize card name by stripping whitespace."""
        if isinstance(v, str):
            return v.strip()
        return v

    @validator("cardNumber", pre=True)
    def normalize_card_number(cls, v: str) -> str:
        """Remove spaces and normalize card number."""
        if isinstance(v, str):
            return "".join(v.split())
        return v

    @validator("expireDate")
    def validate_expire_date(cls, v: str) -> str:
        """Validate expire date format and future date."""
        if not v:
            raise ValueError("Expire date is required")

        try:
            month, year = v.split("/")
            month_int = int(month)
            year_int = int(year) + 2000  # Convert YY to YYYY

            if month_int < 1 or month_int > 12:
                raise ValueError("Invalid month")

            # Check if date is in the future (basic validation)
            from datetime import datetime

            current_year = datetime.now().year
            current_month = datetime.now().month

            if year_int < current_year or (year_int == current_year and month_int < current_month):
                raise ValueError("Card has expired")

        except ValueError as e:
            if "Invalid month" in str(e) or "Card has expired" in str(e):
                raise e
            raise ValueError("Invalid expire date format. Use MM/YY")

        return v

    @validator("cvc")
    def validate_cvc(cls, v: str) -> str:
        """Validate CVC is numeric."""
        if not v.isdigit():
            raise ValueError("CVC must be numeric")
        return v


class PaymentCardCreate(PaymentCardBase):
    """Schema for payment card creation."""

    pass


class PaymentCardUpdate(BaseModel):
    """Schema for payment card update."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    isDefault: Optional[bool] = None
    cardColor: Optional[str] = None

    @validator("name", pre=True)
    def normalize_name(cls, v: Optional[str]) -> Optional[str]:
        """Normalize card name by stripping whitespace."""
        if isinstance(v, str):
            return v.strip() if v.strip() else None
        return v


class PaymentCardInDBBase(BaseModel):
    """Base schema for payment card in DB."""

    id: str
    user_id: UUID
    name: str
    masked_card_number: str
    expire_date: str
    is_default: bool
    card_type: str
    card_color: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        orm_mode = True


class PaymentCardResponse(BaseModel):
    """Payment card schema for responses."""

    id: str
    name: str
    cardNumber: str  # This will be the masked version
    expireDate: str
    cvc: str = "***"  # Always masked in response
    isDefault: bool
    type: str
    cardColor: str

    class Config:
        """Pydantic config."""

        orm_mode = True


class PaymentCard(PaymentCardInDBBase):
    """Payment card schema for responses with full DB data."""

    pass


class MessageResponse(BaseModel):
    """Schema for simple message responses."""

    message: str


class UserActiveResponseUpdate(BaseModel):
    """
    Schema for user activation/deactivation response
    Used when admin toggles user active status
    """

    success: bool
    message: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        # For Pydantic v2 (use this)
        json_schema_extra = {"example": {"success": True, "message": "User activated successfully", "is_active": True}}


class AdminPasswordUpdateRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class MonthlyStat(BaseModel):
    month: str
    monthNumber: int
    averageAmount: float
    totalTransactions: int
    totalVolume: float
    trend: str  # "up", "down", "stable"
    changePercentage: float

    class Config:
        from_attributes = True


class OverallStats(BaseModel):
    totalTransactions: int
    totalVolume: float
    overallAverage: float
    monthOverMonthGrowth: float

    class Config:
        from_attributes = True


class AdminTransactionSummary(BaseModel):
    overallStats: OverallStats
    monthlyStats: List[MonthlyStat]
    lastUpdated: datetime

    class Config:
        from_attributes = True


class MonthlyBalanceStat(BaseModel):
    month: str
    monthNumber: int
    averageBalance: float
    totalBalance: float
    userCount: int
    avgTrend: str
    totalTrend: str
    userTrend: str
    avgChangePercentage: float
    totalChangePercentage: float
    userChangePercentage: float
    newUsers: int

    class Config:
        from_attributes = True


class OverallBalanceStats(BaseModel):
    totalUsers: int
    currentTotalBalance: float
    currentAverageBalance: float
    avgMonthOverMonthGrowth: float
    totalMonthOverMonthGrowth: float
    userMonthOverMonthGrowth: float
    totalNewUsersThisYear: int

    class Config:
        from_attributes = True


class BalanceSummaryResponse(BaseModel):
    monthlyStats: List[MonthlyBalanceStat]
    overallStats: OverallBalanceStats
    lastUpdated: datetime

    class Config:
        from_attributes = True


class UserMonthlyStats(BaseModel):
    name: str
    received: float
    sent: float
    revenue: float


# Add these schemas to your schemas.py file


# =====================================
# Forgot Password Schemas
# =====================================


class ForgotPasswordRequest(BaseModel):
    """Step 1: Request password reset via email."""

    email: EmailStr

    class Config:
        json_schema_extra = {"example": {"email": "user@example.com"}}


class ForgotPasswordVerifyCode(BaseModel):
    """Step 2: Verify the reset code."""

    email: EmailStr
    verify_code: str = Field(..., min_length=6, max_length=6)

    @validator("verify_code")
    def validate_verify_code(cls, v: str) -> str:
        """Validate verification code is exactly 6 digits."""
        if not v.isdigit():
            raise ValueError("Verification code must be numeric")
        if len(v) != 6:
            raise ValueError("Verification code must be exactly 6 digits")
        return v

    class Config:
        json_schema_extra = {"example": {"email": "user@example.com", "verify_code": "123456"}}


class ForgotPasswordReset(BaseModel):
    """Step 3: Reset password with verified code."""

    email: EmailStr
    verify_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    confirm_password: str = Field(..., min_length=8, description="Confirm new password")

    @validator("verify_code")
    def validate_verify_code(cls, v: str) -> str:
        """Validate verification code is exactly 6 digits."""
        if not v.isdigit():
            raise ValueError("Verification code must be numeric")
        if len(v) != 6:
            raise ValueError("Verification code must be exactly 6 digits")
        return v

    @validator("confirm_password")
    def passwords_match(cls, v: str, values: dict) -> str:
        """Validate that passwords match."""
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "verify_code": "123456",
                "new_password": "newPassword123",
                "confirm_password": "newPassword123",
            }
        }


class ForgotPasswordResponse(BaseModel):
    """Generic response for forgot password operations."""

    success: bool
    message: str
    verified_code: str

    class Config:
        json_schema_extra = {"example": {"success": True, "message": "Password reset code sent to your email"}}
