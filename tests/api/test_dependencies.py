from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.dependencies import (
    authenticate_user,
    get_current_active_user,
    get_current_admin,
    get_current_user,
    get_current_verified_user,
    require_roles,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.models import User


@pytest.mark.anyio
async def test_authenticate_user_success_email(db_session):
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


@pytest.mark.anyio
async def test_authenticate_user_invalid_password(db_session):
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
async def test_get_current_user_success(db_session):
    user_id = str(uuid4())
    user = User(id=user_id, email="tokenuser@example.com", is_verified=True, hashed_password="x")
    db_session.add(user)
    await db_session.commit()

    token = jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    result = await get_current_user(db=db_session, token=token)
    assert result.id == user_id


@pytest.mark.anyio
async def test_get_current_user_invalid_token(db_session):
    invalid_token = "invalid.token.here"
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, token=invalid_token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_user_missing_sub(db_session):
    token = jwt.encode({}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(db=db_session, token=token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_active_user_raises():
    user = User(id=str(uuid4()), email="inactive@example.com", is_active=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_active_user(current_user=user)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_get_current_verified_user_raises():
    user = User(id=str(uuid4()), email="notverified@example.com", is_active=True, is_verified=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_verified_user(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_get_current_admin_raises():
    user = User(id=str(uuid4()), email="notadmin@example.com", is_active=True, is_admin=False)
    with pytest.raises(HTTPException) as exc:
        await get_current_admin(current_user=user)
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_require_roles_granted():
    user = {"roles": ["admin", "manager"]}

    dep = require_roles(["admin"])
    result = await dep(current_user=user)
    assert result == user


@pytest.mark.anyio
async def test_require_roles_denied():
    user = {"roles": ["user"]}

    dep = require_roles(["admin"])
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403
