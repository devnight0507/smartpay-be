from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_verified_user,
    get_user_by_email,
    get_user_by_phone,
)
from app.core.security import get_password_hash
from app.db.models.models import Transaction, User, Wallet
from app.db.session import get_db
from app.main import app


@pytest.fixture
async def setup_wallets(db_session: AsyncSession):
    dummy_password = get_password_hash("test123")

    sender = User(
        id=str(uuid4()),
        email="sender@example.com",
        phone="13246542",
        is_verified=True,
        hashed_password=dummy_password,
    )
    recipient = User(
        id=str(uuid4()),
        email="receiver@example.com",
        phone="21324654",
        is_verified=True,
        hashed_password=dummy_password,
    )

    db_session.add_all([sender, recipient])
    await db_session.commit()

    sender_wallet = Wallet(user_id=sender.id, balance=100.0)
    recipient_wallet = Wallet(user_id=recipient.id, balance=0.0)
    db_session.add_all([sender_wallet, recipient_wallet])
    await db_session.commit()

    return sender, recipient


@pytest.fixture
async def setup_user_no_wallet(db_session: AsyncSession):
    dummy_password = get_password_hash("test123")

    sender = User(
        id=str(uuid4()),
        email="sender1@example.com",
        phone="13246543",
        is_verified=True,
        hashed_password=dummy_password,
    )
    recipient = User(
        id=str(uuid4()),
        email="receiver1@example.com",
        phone="21324655",
        is_verified=True,
        hashed_password=dummy_password,
    )

    db_session.add_all([sender, recipient])
    await db_session.commit()

    return sender, recipient


@pytest.fixture
async def override_wallet_deps(db_session: AsyncSession, setup_wallets):
    sender, recipient = setup_wallets
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_verified_user] = lambda: sender
    app.dependency_overrides[get_user_by_email] = lambda db, email: None
    app.dependency_overrides[get_user_by_phone] = lambda db, phone: recipient
    return sender, recipient


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides = {}


@pytest.mark.anyio
async def test_get_balance(client: AsyncClient, override_wallet_deps):
    response = await client.get("/api/v1/wallet/balance")
    assert response.status_code == 200
    assert "balance" in response.json()


@pytest.mark.anyio
async def test_top_up_wallet(client: AsyncClient, override_wallet_deps):
    response = await client.post("/api/v1/wallet/top-up", json={"amount": 50})
    assert response.status_code == 200
    assert response.json()["balance"] == 150.0


@pytest.mark.anyio
async def test_transfer_money(client: AsyncClient, override_wallet_deps):
    payload = {"amount": 20, "recipient_identifier": "21324654", "description": "Test transfer"}
    response = await client.post("/api/v1/wallet/transfer", json=payload)
    assert response.status_code == 200
    assert response.json()["amount"] == 20


@pytest.mark.anyio
async def test_get_transactions(client: AsyncClient, db_session: AsyncSession, override_wallet_deps):
    sender, recipient = override_wallet_deps
    tx = Transaction(
        id=str(uuid4()), sender_id=sender.id, recipient_id=recipient.id, amount=30, type="transfer", status="completed"
    )
    db_session.add(tx)
    await db_session.commit()

    res = await client.get("/api/v1/wallet/transactions")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert len(res.json()) >= 1


@pytest.mark.anyio
async def test_get_balance_wallet_not_found(client: AsyncClient, db_session, setup_user_no_wallet):
    sender, _ = setup_user_no_wallet
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_verified_user] = lambda: sender
    res = await client.get("/api/v1/wallet/balance")
    assert res.status_code == 404


@pytest.mark.anyio
async def test_top_up_wallet_not_found(client: AsyncClient, db_session, setup_user_no_wallet):
    sender, _ = setup_user_no_wallet
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_verified_user] = lambda: sender
    res = await client.post("/api/v1/wallet/top-up", json={"amount": 10})
    assert res.status_code == 404


@pytest.mark.anyio
async def test_transfer_insufficient_balance(client: AsyncClient, override_wallet_deps):
    payload = {"amount": 9999, "recipient_identifier": "21324654", "description": "Overdraft"}
    res = await client.post("/api/v1/wallet/transfer", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Insufficient balance"


@pytest.mark.anyio
async def test_transfer_recipient_not_found(client: AsyncClient, db_session, setup_wallets):
    sender, _ = setup_wallets
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_verified_user] = lambda: sender
    app.dependency_overrides[get_user_by_email] = lambda db, email: None
    app.dependency_overrides[get_user_by_phone] = lambda db, phone: None

    payload = {"amount": 10, "recipient_identifier": "ghost@example.com", "description": "No recipient"}

    res = await client.post("/api/v1/wallet/transfer", json=payload)
    assert res.status_code == 404


@pytest.mark.anyio
async def test_transfer_sender_wallet_not_found(client: AsyncClient, db_session, setup_user_no_wallet):
    sender, recipient = setup_user_no_wallet
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_verified_user] = lambda: sender
    app.dependency_overrides[get_user_by_email] = lambda db, email: recipient
    app.dependency_overrides[get_user_by_phone] = lambda db, phone: recipient

    payload = {"amount": 10, "recipient_identifier": recipient.email, "description": "No wallet"}

    res = await client.post("/api/v1/wallet/transfer", json=payload)
    assert res.status_code == 404


@pytest.mark.anyio
async def test_get_transactions_empty(client: AsyncClient, db_session):
    user = User(id=str(uuid4()), email="empty@example.com", is_verified=True, hashed_password="x")
    wallet = Wallet(user_id=user.id, balance=0.0)
    db_session.add_all([user, wallet])
    await db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_verified_user] = lambda: user

    res = await client.get("/api/v1/wallet/transactions")
    assert res.status_code == 200
    assert res.json() == []
