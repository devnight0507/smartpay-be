from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    fullname = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    notif_setting = Column(String, nullable=True, default="system")
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    sent_transactions = relationship("Transaction", back_populates="sender", foreign_keys="Transaction.sender_id")
    received_transactions = relationship(
        "Transaction",
        back_populates="recipient",
        foreign_keys="Transaction.recipient_id",
    )
    verification_codes = relationship("VerificationCode", back_populates="user")
    payment_cards = relationship("PaymentCard", back_populates="user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Wallet(Base):
    """Wallet model."""

    __tablename__ = "wallets"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="wallet")


class Transaction(Base):
    """Transaction model."""

    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    sender_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recipient_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    card_id = Column(String, nullable=True)
    description = Column(String, nullable=True)
    type = Column(String, nullable=False)  # "transfer", "deposit", "withdrawal"
    status = Column(String, default="completed")  # "pending", "completed", "failed"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    sender = relationship("User", back_populates="sent_transactions", foreign_keys=[sender_id])
    recipient = relationship("User", back_populates="received_transactions", foreign_keys=[recipient_id])


class VerificationCode(Base):
    """Verification code model."""

    __tablename__ = "verification_codes"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    code = Column(String, nullable=False)
    type = Column(String, nullable=False)  # "email", "phone"
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="verification_codes")


class PaymentCard(Base):
    __tablename__ = "payment_cards"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    card_number_hash = Column(String(255), nullable=False)  # Hashed card number
    masked_card_number = Column(String(50), nullable=False)  # Masked display version
    expire_date = Column(String(5), nullable=False)  # MM/YY format
    cvc_hash = Column(String(255), nullable=False)  # Hashed CVC
    is_default = Column(Boolean, default=False, nullable=False)
    card_type = Column(String(20), nullable=False)  # visa, mastercard, amex, etc.
    card_color = Column(String(50), default="bg-blue-500", nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    user = relationship("User", back_populates="payment_cards")


class Notification(Base):
    """Notification model."""

    __tablename__ = "notifications"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(String, nullable=False)
    type = Column(String(50), default="system")  # e.g., "transaction", "system"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    extra_data = Column(JSONB, nullable=True)

    # Relationship
    user = relationship("User", back_populates="notifications")


class RateLimitLog(Base):
    """Rate limiting log for tracking API requests."""

    __tablename__ = "rate_limit_logs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    email = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False)  # e.g., "forgot_password_send_code"
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
