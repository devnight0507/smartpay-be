"""
Simplified test file for profile API endpoints.
Place this file in: tests/api/routes/v1/
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.responses import JSONResponse

# Import the functions under test
from app.api.routes.v1.profile import (
    MONTH_NAMES,
    create_verification_code,
    get_monthly_transaction_summary,
    update_phone,
)


# Simple mock classes
class MockPhoneRequest:
    def __init__(self, phone):
        self.phone = phone


class MockPasswordRequest:
    def __init__(self, current_password, new_password):
        self.currentPassword = current_password
        self.newPassword = new_password


class MockUser:
    def __init__(self):
        self.id = "user-123"
        self.email = "test@example.com"
        self.phone = "+1234567890"
        self.is_verified = True
        self.hashed_password = "hashed_password"


class TestProfileSimple:
    """Simplified profile tests."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        return MockUser()

    # Test utility functions first (no async/DB dependencies)
    def test_month_names_constant(self):
        """Test MONTH_NAMES constant."""
        assert len(MONTH_NAMES) == 12
        assert MONTH_NAMES[1] == "Jan"
        assert MONTH_NAMES[12] == "Dec"

    # Test phone update with basic cases
    @pytest.mark.asyncio
    async def test_update_phone_empty_phone_error(self, mock_db, mock_user):
        """Test phone update with empty phone returns error."""
        phone_data = MockPhoneRequest(phone="   ")  # Whitespace

        result = await update_phone(phone_data=phone_data, db=mock_db, current_user=mock_user)

        # Should return JSONResponse with error
        assert isinstance(result, JSONResponse)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_update_phone_success_basic(self, mock_db, mock_user):
        """Test basic successful phone update."""
        phone_data = MockPhoneRequest(phone="+1987654321")

        # Mock no existing user with same phone
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.profile.create_verification_code") as mock_create_code:
            mock_create_code.return_value = Mock()

            result = await update_phone(phone_data=phone_data, db=mock_db, current_user=mock_user)

            # Should return success response
            assert result["success"] is True
            assert "verification code" in result["message"]

            # Verify user phone was updated
            assert mock_user.phone == "+1987654321"

            # Verify database operations
            mock_db.commit.assert_called_once()
            mock_create_code.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_phone_already_exists(self, mock_db, mock_user):
        """Test phone update when phone already exists."""
        phone_data = MockPhoneRequest(phone="+1987654321")

        # Mock existing user with same phone
        existing_user = MockUser()
        existing_user.id = "other-user"
        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = existing_user
        mock_db.execute.return_value = mock_result

        result = await update_phone(phone_data=phone_data, db=mock_db, current_user=mock_user)

        # Should return error response
        assert isinstance(result, JSONResponse)
        assert result.status_code == 400

    # Test verification code creation
    @pytest.mark.asyncio
    async def test_create_verification_code_basic(self, mock_db):
        """Test basic verification code creation."""
        with (
            patch("random.choices", return_value=["1", "2", "3", "4", "5", "6"]),
            patch("uuid.uuid4") as mock_uuid,
            patch("builtins.print"),
        ):  # Mock the print statement

            mock_uuid.return_value.__str__ = Mock(return_value="verification-123")

            await create_verification_code(mock_db, "user-123", "phone")

            # Verify database operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    # Test monthly summary basic functionality
    @pytest.mark.asyncio
    async def test_get_monthly_summary_basic(self, mock_db, mock_user):
        """Test basic monthly summary retrieval."""
        # Mock empty database result
        mock_result = Mock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.profile.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 3, 15)  # March

            result = await get_monthly_transaction_summary(db=mock_db, current_user=mock_user)

            # Should return 3 months (Jan, Feb, Mar) with zero values
            assert len(result) == 3
            for month_data in result:
                assert month_data.received == 0.0
                assert month_data.sent == 0.0
                assert month_data.revenue == 0.0

    @pytest.mark.asyncio
    async def test_get_monthly_summary_with_data(self, mock_db, mock_user):
        """Test monthly summary with actual data."""
        # Mock database result with one month of data
        mock_row = Mock()
        mock_row.month = 2  # February
        mock_row.received = 500.0
        mock_row.sent = 200.0

        mock_result = Mock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.profile.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 2, 15)  # February

            result = await get_monthly_transaction_summary(db=mock_db, current_user=mock_user)

            # Should return 2 months (Jan, Feb)
            assert len(result) == 2

            # January should be zeros
            jan_data = result[0]
            assert jan_data.name == "Jan"
            assert jan_data.received == 0.0

            # February should have data
            feb_data = result[1]
            assert feb_data.name == "Feb"
            assert feb_data.received == 500.0
            assert feb_data.sent == 200.0
            assert feb_data.revenue == 300.0  # 500 - 200


class TestPhoneVerificationLogic:
    """Test phone verification status logic."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_phone_verified_user_becomes_unverified(self, mock_db):
        """Test that phone-verified user becomes unverified when changing phone."""
        # User verified via phone (no email)
        user = MockUser()
        user.email = None
        user.is_verified = True

        phone_data = MockPhoneRequest(phone="+1987654321")

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.profile.create_verification_code"):
            result = await update_phone(phone_data=phone_data, db=mock_db, current_user=user)

            # User should become unverified
            assert user.is_verified is False
            assert result["is_verified"] is False

    @pytest.mark.asyncio
    async def test_email_verified_user_stays_verified(self, mock_db):
        """Test that email-verified user stays verified when changing phone."""
        # User verified via email
        user = MockUser()
        user.email = "test@example.com"
        user.is_verified = True

        phone_data = MockPhoneRequest(phone="+1987654321")

        mock_result = Mock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.profile.create_verification_code"):
            result = await update_phone(phone_data=phone_data, db=mock_db, current_user=user)

            # User should remain verified
            assert user.is_verified is True
            assert result["is_verified"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
