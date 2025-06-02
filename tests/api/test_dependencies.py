from datetime import datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from jose import jwt

from app.api.dependencies import (
    authenticate_user,
    check_rate_limit,
    get_current_active_user,
    get_current_admin,
    get_current_user,
    get_current_verified_user,
    get_user_by_email,
    get_user_by_phone,
    require_roles,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.models import RateLimitLog, User
from app.schemas.schemas import TokenPayload


@pytest.mark.anyio
async def test_authenticate_user_success_email(db_session):
    """Test successful authentication with email."""
    password = "secure123"
    user = User(
        id=str(uuid4()),
        email="test@example.com",
        phone="000000",
        hashed_password=get_password_hash(password),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    authenticated = await authenticate_user(db_session, "test@example.com", password)
    assert authenticated is not None
    assert authenticated.email == "test@example.com"


@pytest.mark.anyio
async def test_authenticate_user_success_phone(db_session):
    """Test successful authentication with phone."""
    password = "secure123"
    user = User(
        id=str(uuid4()),
        email="test2@example.com",
        phone="123456",
        hashed_password=get_password_hash(password),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    authenticated = await authenticate_user(db_session, "123456", password)
    assert authenticated is not None
    assert authenticated.phone == "123456"


@pytest.mark.anyio
async def test_authenticate_user_invalid_password(db_session):
    """Test authentication with invalid password."""
    user = User(
        id=str(uuid4()),
        email="wrongpass@example.com",
        phone="999999",
        hashed_password=get_password_hash("correct"),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    authenticated = await authenticate_user(db_session, "wrongpass@example.com", "wrong")
    assert authenticated is None


@pytest.mark.anyio
async def test_authenticate_user_nonexistent_user(db_session):
    """Test authentication with non-existent user."""
    authenticated = await authenticate_user(db_session, "nonexistent@example.com", "password")
    assert authenticated is None


@pytest.mark.anyio
async def test_get_user_by_email_success(db_session):
    """Test getting user by email."""
    user = User(
        id=str(uuid4()),
        email="email_test@example.com",
        phone="111111",
        hashed_password="dummy",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    result = await get_user_by_email(db_session, "email_test@example.com")
    assert result is not None
    assert result.email == "email_test@example.com"


@pytest.mark.anyio
async def test_get_user_by_email_not_found(db_session):
    """Test getting user by email when user doesn't exist."""
    result = await get_user_by_email(db_session, "nonexistent@example.com")
    assert result is None


@pytest.mark.anyio
async def test_get_user_by_phone_success(db_session):
    """Test getting user by phone."""
    user = User(
        id=str(uuid4()),
        email="phone_test@example.com",
        phone="222222",
        hashed_password="dummy",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    result = await get_user_by_phone(db_session, "222222")
    assert result is not None
    assert result.phone == "222222"


@pytest.mark.anyio
async def test_get_user_by_phone_not_found(db_session):
    """Test getting user by phone when user doesn't exist."""
    result = await get_user_by_phone(db_session, "999999999")
    assert result is None


@pytest.mark.anyio
async def test_get_current_user_success(db_session):
    """Test successful token validation and user retrieval."""
    user_id = str(uuid4())
    user = User(id=user_id, email="tokenuser@example.com", is_verified=True, hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    token = jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    result = await get_current_user(db=db_session, token=token)
    assert result.id == user_id


@pytest.mark.anyio
async def test_get_current_user_invalid_token(db_session):
    """Test get_current_user with invalid token."""
    invalid_token = "invalid.token.here"
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, token=invalid_token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_user_missing_sub(db_session):
    """Test get_current_user with token missing 'sub' claim."""
    token = jwt.encode({}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, token=token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_user_nonexistent_user(db_session):
    """Test get_current_user with valid token but non-existent user."""
    fake_user_id = str(uuid4())
    token = jwt.encode({"sub": fake_user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, token=token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_active_user_success():
    """Test get_current_active_user with active user."""
    user = User(id=str(uuid4()), email="active@example.com", is_active=True)
    result = await get_current_active_user(current_user=user)
    assert result == user


@pytest.mark.anyio
async def test_get_current_active_user_inactive():
    """Test get_current_active_user with inactive user."""
    user = User(id=str(uuid4()), email="inactive@example.com", is_active=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_active_user(current_user=user)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_get_current_verified_user_success():
    """Test get_current_verified_user with verified user."""
    user = User(id=str(uuid4()), email="verified@example.com", is_active=True, is_verified=True)
    result = await get_current_verified_user(current_user=user)
    assert result == user


@pytest.mark.anyio
async def test_get_current_verified_user_unverified():
    """Test get_current_verified_user with unverified user."""
    user = User(id=str(uuid4()), email="notverified@example.com", is_active=True, is_verified=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_verified_user(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_get_current_admin_success():
    """Test get_current_admin with admin user."""
    user = User(id=str(uuid4()), email="admin@example.com", is_active=True, is_admin=True)
    result = await get_current_admin(current_user=user)
    assert result == user


@pytest.mark.anyio
async def test_get_current_admin_not_admin():
    """Test get_current_admin with non-admin user."""
    user = User(id=str(uuid4()), email="notadmin@example.com", is_active=True, is_admin=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_admin(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_require_roles_multiple_roles_success():
    """Test require_roles with user having one of multiple required roles."""
    user = {"roles": ["manager", "editor"]}

    dep = require_roles(["admin", "manager"])
    result = await dep(current_user=user)
    assert result == user


@pytest.mark.anyio
async def test_require_roles_no_roles():
    """Test require_roles with user having no roles."""
    user = {"roles": []}

    dep = require_roles(["admin"])
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_require_roles_missing_roles_key():
    """Test require_roles with user missing roles key."""
    user = {}

    dep = require_roles(["admin"])
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_require_roles_insufficient_permissions():
    """Test require_roles with user lacking required role."""
    user = {"roles": ["user"]}

    dep = require_roles(["admin"])
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_check_rate_limit_first_attempt(db_session):
    """Test rate limit check on first attempt."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "127.0.0.1"

    # Should pass without raising exception on first attempt
    await check_rate_limit(
        request=request,
        db=db_session,
        email="test@example.com",
        endpoint="test_endpoint",
        max_attempts=3,
        window_minutes=60,
    )

    # Verify log was created
    from sqlalchemy.future import select

    query = select(RateLimitLog).where(RateLimitLog.email == "test@example.com")
    result = await db_session.execute(query)
    log = result.scalars().first()
    assert log is not None
    assert log.email == "test@example.com"
    assert log.endpoint == "test_endpoint"
    assert log.ip_address == "127.0.0.1"


@pytest.mark.anyio
async def test_check_rate_limit_within_limit(db_session):
    """Test rate limit check when within allowed attempts."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "192.168.1.1"

    # Create some existing logs within the window
    for i in range(2):  # 2 attempts, limit is 3
        log = RateLimitLog(
            id=str(uuid4()),
            email="within@example.com",
            endpoint="test_endpoint",
            ip_address="192.168.1.1",
            created_at=datetime.utcnow() - timedelta(minutes=10),
        )
        db_session.add(log)
    await db_session.commit()

    # Should pass on 3rd attempt
    await check_rate_limit(
        request=request,
        db=db_session,
        email="within@example.com",
        endpoint="test_endpoint",
        max_attempts=3,
        window_minutes=60,
    )


@pytest.mark.anyio
async def test_check_rate_limit_exceeded(db_session):
    """Test rate limit when max attempts exceeded."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "10.0.0.1"

    # Create logs that exceed the limit
    oldest_time = datetime.utcnow() - timedelta(minutes=30)
    for i in range(3):  # 3 attempts, limit is 3
        log = RateLimitLog(
            id=str(uuid4()),
            email="exceeded@example.com",
            endpoint="test_endpoint",
            ip_address="10.0.0.1",
            created_at=oldest_time if i == 0 else datetime.utcnow() - timedelta(minutes=10),
        )
        db_session.add(log)
    await db_session.commit()

    # Should raise 429 error
    with pytest.raises(HTTPException) as exc:
        await check_rate_limit(
            request=request,
            db=db_session,
            email="exceeded@example.com",
            endpoint="test_endpoint",
            max_attempts=3,
            window_minutes=60,
        )
    assert exc.value.status_code == 429
    assert "Too many attempts" in exc.value.detail


@pytest.mark.anyio
async def test_check_rate_limit_old_attempts_ignored(db_session):
    """Test that old attempts outside the window are ignored."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "172.16.0.1"

    # Create old logs outside the window
    old_time = datetime.utcnow() - timedelta(minutes=120)  # 2 hours ago
    for i in range(5):  # 5 old attempts
        log = RateLimitLog(
            id=str(uuid4()),
            email="old@example.com",
            endpoint="test_endpoint",
            ip_address="172.16.0.1",
            created_at=old_time,
        )
        db_session.add(log)
    await db_session.commit()

    # Should pass since old attempts are outside the window
    await check_rate_limit(
        request=request,
        db=db_session,
        email="old@example.com",
        endpoint="test_endpoint",
        max_attempts=3,
        window_minutes=60,
    )


@pytest.mark.anyio
async def test_check_rate_limit_no_client_ip(db_session):
    """Test rate limit check when request has no client IP."""
    request = Mock(spec=Request)
    request.client = None

    await check_rate_limit(
        request=request,
        db=db_session,
        email="noclient@example.com",
        endpoint="test_endpoint",
        max_attempts=3,
        window_minutes=60,
    )

    # Verify log was created with "unknown" IP
    from sqlalchemy.future import select

    query = select(RateLimitLog).where(RateLimitLog.email == "noclient@example.com")
    result = await db_session.execute(query)
    log = result.scalars().first()
    assert log is not None
    assert log.ip_address == "unknown"


@pytest.mark.anyio
async def test_check_rate_limit_different_endpoints(db_session):
    """Test that rate limits are separate for different endpoints."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "203.0.113.1"

    # Create max attempts for endpoint1
    for i in range(3):
        log = RateLimitLog(
            id=str(uuid4()),
            email="multi@example.com",
            endpoint="endpoint1",
            ip_address="203.0.113.1",
            created_at=datetime.utcnow() - timedelta(minutes=10),
        )
        db_session.add(log)
    await db_session.commit()

    # Should still allow attempts on endpoint2
    await check_rate_limit(
        request=request,
        db=db_session,
        email="multi@example.com",
        endpoint="endpoint2",
        max_attempts=3,
        window_minutes=60,
    )


@pytest.mark.anyio
async def test_token_payload_validation():
    """Test TokenPayload schema validation."""
    # Test with valid payload
    payload = {"sub": str(uuid4())}
    token_data = TokenPayload(**payload)
    assert token_data.sub is not None

    # Test with None sub - should still work due to Optional type
    payload_none = {"sub": None}
    token_data_none = TokenPayload(**payload_none)
    assert token_data_none.sub is None


@pytest.mark.anyio
async def test_authenticate_user_with_empty_credentials(db_session):
    """Test authentication with empty username/password."""
    result = await authenticate_user(db_session, "", "")
    assert result is None

    result = await authenticate_user(db_session, "test@example.com", "")
    assert result is None


@pytest.mark.anyio
async def test_check_rate_limit_zero_count_handling(db_session):
    """Test rate limit when database returns None for count."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "198.51.100.1"

    # Should handle the case where count returns None gracefully
    await check_rate_limit(
        request=request,
        db=db_session,
        email="zerocount@example.com",
        endpoint="test_endpoint",
        max_attempts=3,
        window_minutes=60,
    )
