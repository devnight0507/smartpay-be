# from uuid import uuid4

# import pytest
# from httpx import AsyncClient
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.dependencies import get_current_active_user
# from app.db.models.models import PaymentCard, User
# from app.main import app


# @pytest.fixture
# async def card_user(db_session: AsyncSession):
#     user = User(
#         id=str(uuid4()),
#         email="carduser@example.com",
#         fullname="Card User",
#         hashed_password="cardpass",
#         is_verified=True,
#         is_active=True,
#     )
#     db_session.add(user)
#     await db_session.commit()
#     return user


# @pytest.fixture(autouse=True)
# def clear_dependency_overrides():
#     yield
#     app.dependency_overrides = {}


# @pytest.mark.anyio
# async def test_add_new_card(client: AsyncClient, db_session: AsyncSession, card_user):
#     app.dependency_overrides[get_current_active_user] = lambda: card_user
#     payload = {
#         "name": "My Visa",
#         "cardNumber": "4111111111111111",
#         "expireDate": "12/50",
#         "cvc": "123",
#         "isDefault": True,
#         "type": "visa",
#         "cardColor": "bg-blue-500",
#     }
#     res = await client.post("/api/v1/payment-card/", json=payload)
#     assert res.status_code == 200
#     assert "id" in res.json()


# @pytest.mark.anyio
# async def test_get_all_cards(client: AsyncClient, db_session: AsyncSession, card_user):
#     app.dependency_overrides[get_current_active_user] = lambda: card_user
#     # Add a card first
#     card = PaymentCard(
#         id=str(uuid4()),
#         user_id=card_user.id,
#         name="Test Card",
#         card_number_hash="hash",
#         masked_card_number="**** **** **** 1111",
#         expire_date="12/50",
#         cvc_hash="hash",
#         is_default=True,
#         card_type="visa",
#         card_color="bg-blue-500",
#         is_deleted=False,
#     )
#     db_session.add(card)
#     await db_session.commit()
#     res = await client.get("/api/v1/payment-card/")
#     assert res.status_code == 200
#     assert isinstance(res.json(), list)
#     assert any(c["cardNumber"] == "**** **** **** 1111" for c in res.json())
