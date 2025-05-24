from datetime import timedelta

from jose import jwt

from app.core import security
from app.core.config import settings


def test_create_access_token_with_expiry():
    token = security.create_access_token("user123", expires_delta=timedelta(minutes=10))
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == "user123"
    assert "exp" in decoded


def test_create_access_token_default_expiry():
    token = security.create_access_token("user456")
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded["sub"] == "user456"
    assert "exp" in decoded


def test_password_hash_and_verify():
    raw_password = "supersecret123"
    hashed = security.get_password_hash(raw_password)
    assert isinstance(hashed, str)
    assert security.verify_password(raw_password, hashed)
    assert not security.verify_password("wrongpassword", hashed)
