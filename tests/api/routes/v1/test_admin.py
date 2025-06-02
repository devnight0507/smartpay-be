# from uuid import uuid4

# import pytest
# from httpx import AsyncClient
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.dependencies import get_current_admin
# from app.db.models.models import User, Wallet
# from app.main import app


# @pytest.fixture
# async def admin_user(db_session: AsyncSession):
#     admin = User(
#         id=str(uuid4()),
#         email="admin@example.com",
#         fullname="Admin User",
#         hashed_password="adminpass",
#         is_verified=True,
#         is_active=True,
#         is_admin=True,
#     )
#     db_session.add(admin)
#     await db_session.commit()
#     wallet = Wallet(id=str(uuid4()), user_id=admin.id, balance=1000.0)
#     db_session.add(wallet)
#     await db_session.commit()
#     return admin


# @pytest.fixture(autouse=True)
# def clear_dependency_overrides():
#     yield
#     app.dependency_overrides = {}


# @pytest.mark.anyio
# async def test_get_users(client: AsyncClient, db_session: AsyncSession, admin_user):
#     app.dependency_overrides[get_current_admin] = lambda: admin_user
#     res = await client.get("/api/v1/admin/users")
#     assert res.status_code == 200
#     assert isinstance(res.json(), list)


# @pytest.mark.anyio
# async def test_get_balance_summary(client: AsyncClient, db_session: AsyncSession, admin_user):
#     app.dependency_overrides[get_current_admin] = lambda: admin_user
#     res = await client.get("/api/v1/admin/balances/summary")
#     assert res.status_code == 200
#     assert "overallStats" in res.json()


# @pytest.mark.anyio
# async def test_get_admin_transaction_summary(client: AsyncClient, db_session: AsyncSession, admin_user):
#     app.dependency_overrides[get_current_admin] = lambda: admin_user
#     res = await client.get("/api/v1/admin/transactions/summary")
#     assert res.status_code == 200
#     assert "overallStats" in res.json()
