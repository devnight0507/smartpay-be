"""
Simplified test file for wallet API endpoints.
Place this file in: tests/api/routes/v1/
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

# Import the functions under test
from app.api.routes.v1.wallet import (
    get_balance,
    get_transactions,
    top_up_wallet,
    transfer_money,
    withdraw_wallet,
)


# Simple mock classes to avoid Pydantic validation issues
class MockTopUpData:
    def __init__(self, amount, card_id):
        self.amount = amount
        self.card_id = card_id


class MockTransactionData:
    def __init__(self, recipient_identifier, amount, description=None):
        self.recipient_identifier = recipient_identifier
        self.amount = amount
        self.description = description


class MockUser:
    def __init__(self, user_id="user-123"):
        self.id = user_id
        self.email = "test@example.com"
        self.fullname = "Test User"


class MockWallet:
    def __init__(self, user_id="user-123", balance=1000.0):
        self.id = "wallet-123"
        self.user_id = user_id
        self.balance = Decimal(str(balance))


class MockTransaction:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "txn-123")
        self.sender_id = kwargs.get("sender_id", "user-123")
        self.recipient_id = kwargs.get("recipient_id", "user-456")
        self.amount = kwargs.get("amount", Decimal("100.00"))
        self.type = kwargs.get("type", "transfer")
        self.status = kwargs.get("status", "completed")
        self.sender = kwargs.get("sender", None)
        self.recipient = kwargs.get("recipient", None)


class TestWalletSimple:
    """Simplified wallet tests without complex mocking."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        return MockUser()

    @pytest.fixture
    def mock_wallet(self):
        return MockWallet()

    @pytest.mark.asyncio
    async def test_get_balance_success(self, mock_db, mock_user, mock_wallet):
        """Test successful balance retrieval."""
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_wallet
        mock_db.execute.return_value = mock_result

        result = await get_balance(db=mock_db, current_user=mock_user)

        assert result == mock_wallet
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_balance_wallet_not_found(self, mock_db, mock_user):
        """Test balance retrieval when wallet doesn't exist."""
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_balance(db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Wallet not found"

    @pytest.mark.asyncio
    async def test_top_up_wallet_success(self, mock_db, mock_user, mock_wallet):
        """Test successful wallet top up."""
        top_up_data = MockTopUpData(amount=500.0, card_id="card-123")
        initial_balance = float(mock_wallet.balance)

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_wallet
        mock_db.execute.return_value = mock_result

        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.__str__ = Mock(return_value="transaction-123")

            result = await top_up_wallet(top_up_data=top_up_data, db=mock_db, current_user=mock_user)

            # Verify wallet balance was updated
            assert mock_wallet.balance == initial_balance + top_up_data.amount

            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

            assert result == mock_wallet

    @pytest.mark.asyncio
    async def test_top_up_wallet_not_found(self, mock_db, mock_user):
        """Test top up when wallet doesn't exist."""
        top_up_data = MockTopUpData(amount=500.0, card_id="card-123")

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await top_up_wallet(top_up_data=top_up_data, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Wallet not found"

    @pytest.mark.asyncio
    async def test_withdraw_wallet_success(self, mock_db, mock_user, mock_wallet):
        """Test successful wallet withdrawal."""
        withdraw_data = MockTopUpData(amount=300.0, card_id="card-123")
        initial_balance = float(mock_wallet.balance)

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_wallet
        mock_db.execute.return_value = mock_result

        with patch("uuid.uuid4"):
            result = await withdraw_wallet(withdraw=withdraw_data, db=mock_db, current_user=mock_user)

            # Verify wallet balance was updated
            assert mock_wallet.balance == initial_balance - withdraw_data.amount

            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

            assert result == mock_wallet

    @pytest.mark.asyncio
    async def test_withdraw_wallet_negative_amount(self, mock_db, mock_user):
        """Test withdrawal with negative amount."""
        withdraw_data = MockTopUpData(amount=-100.0, card_id="card-123")

        with pytest.raises(HTTPException) as exc_info:
            await withdraw_wallet(withdraw=withdraw_data, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Amount must be positive"

    @pytest.mark.asyncio
    async def test_withdraw_wallet_insufficient_balance(self, mock_db, mock_user):
        """Test withdrawal with insufficient balance."""
        withdraw_data = MockTopUpData(amount=1500.0, card_id="card-123")
        mock_wallet = MockWallet(balance=1000.0)  # Less than withdrawal amount

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = mock_wallet
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await withdraw_wallet(withdraw=withdraw_data, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Insufficient balance"

    @pytest.mark.asyncio
    async def test_transfer_money_insufficient_balance(self, mock_db, mock_user):
        """Test transfer with insufficient balance."""
        transaction_data = MockTransactionData(
            recipient_identifier="recipient@example.com",
            amount=1500.0,  # More than available balance
            description="Test transfer",
        )

        sender_wallet = MockWallet(balance=1000.0)
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = sender_wallet
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await transfer_money(transaction_data=transaction_data, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Insufficient balance"

    @pytest.mark.asyncio
    async def test_transfer_money_sender_wallet_not_found(self, mock_db, mock_user):
        """Test transfer when sender wallet doesn't exist."""
        transaction_data = MockTransactionData(
            recipient_identifier="recipient@example.com", amount=200.0, description="Test transfer"
        )

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await transfer_money(transaction_data=transaction_data, db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sender wallet not found"

    @pytest.mark.asyncio
    async def test_get_transactions_success(self, mock_db, mock_user):
        """Test successful transaction retrieval."""
        transactions = [
            MockTransaction(id="txn-1", amount=Decimal("100.00")),
            MockTransaction(id="txn-2", amount=Decimal("200.00")),
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = transactions
        mock_db.execute.return_value = mock_result

        result = await get_transactions(limit=50, offset=0, db=mock_db, current_user=mock_user)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result == transactions
        mock_db.execute.assert_called_once()
