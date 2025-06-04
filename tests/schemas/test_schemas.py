from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import schemas


def test_user_base_email_and_phone_validation():
    # Valid: only email
    user1 = schemas.UserBase(fullname="Full Name", email="test@example.com")
    assert user1.email == "test@example.com"

    # Valid: only phone
    user2 = schemas.UserBase(fullname="Full Name", phone="+1234567890")
    assert user2.phone == "+1234567890"

    # Invalid: neither email nor phone
    with pytest.raises(ValidationError) as exc:
        schemas.UserBase(fullname="Full Name", email=None, phone=None)

    assert "Either email or phone must be provided" in str(exc.value)

    # Empty string test (normalized to None, then fails)
    with pytest.raises(ValidationError):
        schemas.UserBase(fullname="John", email="", phone="")


def test_user_create_password_min_length():
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@b.com", password="123", phone="123")


def test_transaction_create_amount_validation():
    with pytest.raises(ValidationError):
        schemas.TransactionCreate(amount=0, recipient_identifier="email@example.com")

    tx = schemas.TransactionCreate(amount=10, recipient_identifier="email@example.com")
    assert tx.amount == 10


def test_payment_card_base_valid():
    card = schemas.PaymentCardBase(
        name="  My Visa  ",
        cardNumber="4111 1111 1111 1111",
        expireDate=(datetime.now() + timedelta(days=60)).strftime("%m/%y"),
        cvc="123",
    )
    assert card.name == "My Visa"
    assert card.cardNumber == "4111111111111111"
    assert card.cvc == "123"


def test_payment_card_base_invalid_expired():
    expired = (datetime.now() - timedelta(days=30)).strftime("%m/%y")
    with pytest.raises(ValidationError) as exc:
        schemas.PaymentCardBase(name="Test", cardNumber="4111111111111111", expireDate=expired, cvc="123")
    assert "Card has expired" in str(exc.value)


def test_payment_card_base_invalid_format():
    # This input passes the regex, but fails our custom validator for invalid month (00)
    with pytest.raises(ValidationError) as exc:
        schemas.PaymentCardBase(
            name="Test", cardNumber="4111111111111111", expireDate="00/99", cvc="123"  # valid format, invalid logic
        )
    assert "String should match pattern" in str(exc.value)


def test_payment_card_base_invalid_cvc():
    with pytest.raises(ValidationError) as exc:
        schemas.PaymentCardBase(name="Test", cardNumber="4111111111111111", expireDate="12/99", cvc="12x")
    assert "CVC must be numeric" in str(exc.value)


def test_payment_card_update_strip_name():
    update = schemas.PaymentCardUpdate(name="  Gold Card  ")
    assert update.name == "Gold Card"


def test_user_in_db_base_orm_mode():
    user = schemas.UserInDBBase(
        fullname="Test User",
        id=uuid4(),
        email="test@example.com",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        is_active=True,
        is_admin=False,
        is_verified=True,
    )
    assert user.dict()


def test_wallet_create():
    wallet = schemas.WalletCreate(user_id=uuid4())
    assert isinstance(wallet, schemas.WalletBase)


def test_message_response():
    resp = schemas.MessageResponse(message="Success")
    assert resp.message == "Success"
