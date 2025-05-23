# import pytest
# from uuid import uuid4
# from datetime import datetime, timedelta

# from httpx import AsyncClient
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.security import get_password_hash
# from app.db.models.models import User, VerificationCode, Wallet
# from app.api.dependencies import get_current_active_user
# from app.main import app

# @pytest.fixture
# async def registered_user(db_session: AsyncSession):
#     user_id = str(uuid4())
#     user = User(
#         id=user_id,
#         email="user@example.com",
#         phone="1234567890",
#         fullname="John Doe",
#         hashed_password=get_password_hash("secure123"),
#         is_verified=False,
#         is_active=True,
#         is_admin=False
#     )
#     db_session.add(user)
#     await db_session.commit()

#     wallet = Wallet(id=str(uuid4()), user_id=user.id, balance=0.0)
#     db_session.add(wallet)
#     await db_session.commit()

#     code = VerificationCode(
#         id=str(uuid4()),
#         user_id=user.id,
#         code="999999",
#         type="email",
#         is_used=False,
#         expires_at=datetime.utcnow() + timedelta(minutes=5),
#     )
#     db_session.add(code)
#     await db_session.commit()

#     return user, code


# @pytest.mark.anyio
# async def test_register_user_success(client: AsyncClient):
#     payload = {
#         "fullname": "Test User",
#         "email": "newuser@example.com",
#         "phone": "1231231234",
#         "password": "strongpass",
#         "is_active": True,
#         "is_admin": False,
#         "is_verified": False,
#     }
#     res = await client.post("/api/v1/auth/register", json=payload)
#     assert res.status_code == 500
#     data = res.json()
#     assert data['error']['details']['error'] == "newuser@example.com"


# @pytest.mark.anyio
# async def test_register_user_duplicate_email(client: AsyncClient, registered_user):
#     payload = {
#         "fullname": "Test User",
#         "email": "user@example.com",
#         "phone": "0000000000",
#         "password": "strongpass",
#         "is_active": True,
#         "is_admin": False,
#         "is_verified": False,
#     }
#     res = await client.post("/api/v1/auth/register", json=payload)
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_register_user_missing_all(client: AsyncClient):
#     res = await client.post("/api/v1/auth/register", json={"fullname": "X", "password": "12345678"})
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_login_success(client: AsyncClient, registered_user, db_session: AsyncSession):
#     user, _ = registered_user
#     user.is_verified = True
#     await db_session.commit()

#     form = {"username": user.email, "password": "secure123"}
#     res = await client.post("/api/v1/auth/login", data=form)
#     assert res.status_code == 200
#     assert "access_token" in res.json()


# @pytest.mark.anyio
# async def test_login_wrong_password(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     form = {"username": user.email, "password": "wrong"}
#     res = await client.post("/api/v1/auth/login", data=form)
#     assert res.status_code == 401


# @pytest.mark.anyio
# async def test_me_success(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     user.is_verified = True
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.get("/api/v1/auth/me")
#     assert res.status_code == 200
#     assert res.json()["email"] == user.email


# @pytest.mark.anyio
# async def test_verify_code_success(client: AsyncClient, registered_user):
#     user, code = registered_user
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/verify/email", json={"code": code.code})
#     assert res.status_code == 200
#     assert res.json()["is_verified"] is True


# @pytest.mark.anyio
# async def test_verify_code_invalid_code(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/verify/email", json={"code": "wrong"})
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_resend_verification_success(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/resend-verification/email")
#     assert res.status_code == 200


# @pytest.mark.anyio
# async def test_resend_already_verified(client: AsyncClient, registered_user, db_session: AsyncSession):
#     user, _ = registered_user
#     user.is_verified = True
#     await db_session.commit()
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/resend-verification/email")
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_get_user_found(client: AsyncClient, registered_user, db_session: AsyncSession):
#     user, _ = registered_user
#     user.is_verified = True
#     await db_session.commit()
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.get(f"/api/v1/auth/{user.email}")
#     assert res.status_code == 200
#     assert res.json()["email"] == user.email


# @pytest.mark.anyio
# async def test_get_user_not_found(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.get("/api/v1/auth/ghost@example.com")
#     assert res.status_code == 404


# @pytest.mark.anyio
# async def test_get_user_not_verified(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.get(f"/api/v1/auth/{user.email}")
#     assert res.status_code == 403
# @pytest.mark.anyio
# async def test_register_with_phone_only(client: AsyncClient):
#     res = await client.post("/api/v1/auth/register", json={
#         "fullname": "PhoneOnly",
#         "phone": "1234567899",
#         "password": "secure123"
#     })
#     assert res.status_code == 200
#     assert res.json()["phone"] == "1234567899"


# @pytest.mark.anyio
# async def test_register_existing_phone(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), phone="5555555555",
#         hashed_password=get_password_hash("pass"), is_active=True, is_verified=False
#     )
#     db_session.add(user)
#     await db_session.commit()

#     res = await client.post("/api/v1/auth/register", json={
#         "fullname": "Dup Phone",
#         "phone": "5555555555",
#         "password": "pass"
#     })
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_login_inactive_user(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), email="inactive@example.com",
#         hashed_password=get_password_hash("secure123"),
#         is_active=False, is_verified=True,
#     )
#     db_session.add(user)
#     await db_session.commit()

#     res = await client.post("/api/v1/auth/login", data={"username": user.email, "password": "secure123"})
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_verify_expired_code(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), email="expired@example.com",
#         hashed_password=get_password_hash("123456"),
#         is_active=True, is_verified=False,
#     )
#     db_session.add(user)
#     await db_session.commit()

#     code = VerificationCode(
#         id=str(uuid4()), user_id=user.id,
#         code="111111", type="email",
#         is_used=False, expires_at=datetime.utcnow() - timedelta(seconds=1)
#     )
#     db_session.add(code)
#     await db_session.commit()

#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/verify/email", json={"code": "111111"})
#     assert res.status_code == 400
#     assert "No valid verification code" in res.json()["detail"]


# @pytest.mark.anyio
# async def test_verify_already_used_code(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), email="used@example.com",
#         hashed_password=get_password_hash("123456"),
#         is_active=True, is_verified=False,
#     )
#     db_session.add(user)
#     await db_session.commit()

#     code = VerificationCode(
#         id=str(uuid4()), user_id=user.id,
#         code="222222", type="email",
#         is_used=True, expires_at=datetime.utcnow() + timedelta(minutes=5)
#     )
#     db_session.add(code)
#     await db_session.commit()

#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/verify/email", json={"code": "222222"})
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_resend_invalid_type(client: AsyncClient, registered_user):
#     user, _ = registered_user
#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/resend-verification/invalid")
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_resend_no_email(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), phone="9900887766",
#         hashed_password=get_password_hash("123456"),
#         is_verified=False, is_active=True,
#     )
#     db_session.add(user)
#     await db_session.commit()

#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.post("/api/v1/auth/resend-verification/email")
#     assert res.status_code == 400


# @pytest.mark.anyio
# async def test_get_user_verified(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), email="verified@example.com", phone="10101010",
#         hashed_password="x", is_verified=True, is_active=True
#     )
#     db_session.add(user)
#     await db_session.commit()

#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.get(f"/api/v1/auth/{user.email}")
#     assert res.status_code == 200


# @pytest.mark.anyio
# async def test_get_user_unverified(client: AsyncClient, db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()), email="notverified@example.com",
#         hashed_password="x", is_verified=False, is_active=True
#     )
#     db_session.add(user)
#     await db_session.commit()

#     app.dependency_overrides[get_current_active_user] = lambda: user
#     res = await client.get(f"/api/v1/auth/{user.email}")
#     assert res.status_code == 403
