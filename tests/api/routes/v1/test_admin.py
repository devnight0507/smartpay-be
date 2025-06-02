from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.schemas.schemas import (
    AdminPasswordUpdateRequest,
    AdminTransactionSummary,
    BalanceSummaryResponse,
    UserActiveResponseUpdate,
)


class TestAdminRoutes:

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_admin_user(self):
        admin = MagicMock()
        admin.id = str(uuid4())
        admin.email = "admin@test.com"
        admin.is_admin = True
        admin.is_active = True
        return admin

    @pytest.fixture
    def mock_regular_user(self):
        user = MagicMock()
        user.id = str(uuid4())
        user.email = "user@test.com"
        user.is_admin = False
        user.is_active = True
        user.hashed_password = "hashed_password"
        return user

    @pytest.fixture
    def sample_users(self):
        users = []
        for i in range(3):
            user = MagicMock()
            user.id = str(uuid4())
            user.email = f"user{i}@test.com"
            user.is_active = True
            user.is_admin = False
            users.append(user)
        return users

    @pytest.mark.asyncio
    async def test_get_users_success(self, mock_db, mock_admin_user, sample_users):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_users
        mock_db.execute.return_value = mock_result

        with (
            patch("app.api.routes.v1.admin.get_db", return_value=mock_db),
            patch("app.api.routes.v1.admin.get_current_admin", return_value=mock_admin_user),
        ):

            from app.api.routes.v1.admin import get_users

            result = await get_users(db=mock_db, current_admin=mock_admin_user)

            assert result == sample_users
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_users_database_error(self, mock_db, mock_admin_user):
        mock_db.execute.side_effect = SQLAlchemyError("Database connection failed")

        from app.api.routes.v1.admin import get_users

        with pytest.raises(HTTPException) as exc_info:
            await get_users(db=mock_db, current_admin=mock_admin_user)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Database error"

    @pytest.mark.asyncio
    async def test_toggle_user_active_success_activate(self, mock_db, mock_admin_user, mock_regular_user):
        user_id = UUID(mock_regular_user.id)
        mock_regular_user.is_active = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_regular_user
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.admin import toggle_user_active

        result = await toggle_user_active(user_id=user_id, db=mock_db, current_admin=mock_admin_user)

        assert isinstance(result, UserActiveResponseUpdate)
        assert result.success is True
        assert result.is_active is True
        assert "activated" in result.message
        assert mock_regular_user.is_active is True
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_regular_user)

    @pytest.mark.asyncio
    async def test_toggle_user_active_success_deactivate(self, mock_db, mock_admin_user, mock_regular_user):
        user_id = UUID(mock_regular_user.id)
        mock_regular_user.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_regular_user
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.admin import toggle_user_active

        result = await toggle_user_active(user_id=user_id, db=mock_db, current_admin=mock_admin_user)

        assert isinstance(result, UserActiveResponseUpdate)
        assert result.success is True
        assert result.is_active is False
        assert "deactivated" in result.message
        assert mock_regular_user.is_active is False

    @pytest.mark.asyncio
    async def test_toggle_user_active_user_not_found(self, mock_db, mock_admin_user):
        user_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.api.routes.v1.admin import toggle_user_active

        with pytest.raises(HTTPException) as exc_info:
            await toggle_user_active(user_id=user_id, db=mock_db, current_admin=mock_admin_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert f"User with ID {user_id} not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_toggle_user_active_database_error(self, mock_db, mock_admin_user):
        user_id = uuid4()
        mock_db.execute.side_effect = Exception("Database error")

        from app.api.routes.v1.admin import toggle_user_active

        with pytest.raises(HTTPException) as exc_info:
            await toggle_user_active(user_id=user_id, db=mock_db, current_admin=mock_admin_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to update user status" in exc_info.value.detail
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_password_success(self, mock_db, mock_admin_user, mock_regular_user):
        user_id = UUID(mock_regular_user.id)
        payload = AdminPasswordUpdateRequest(new_password="new_secure_password")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_regular_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.routes.v1.admin.get_password_hash", return_value="hashed_new_password") as mock_hash:
            from app.api.routes.v1.admin import update_user_password

            result = await update_user_password(
                user_id=user_id, payload=payload, db=mock_db, current_admin=mock_admin_user
            )

            assert result["message"] == f"Password updated successfully for user {user_id}"
            assert mock_regular_user.hashed_password == "hashed_new_password"
            mock_hash.assert_called_once_with("new_secure_password")
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_password_database_error(self, mock_db, mock_admin_user):
        user_id = uuid4()
        payload = AdminPasswordUpdateRequest(new_password="new_password")

        mock_db.execute.side_effect = Exception("Database error")

        from app.api.routes.v1.admin import update_user_password

        with pytest.raises(HTTPException) as exc_info:
            await update_user_password(user_id=user_id, payload=payload, db=mock_db, current_admin=mock_admin_user)

        assert exc_info.value.status_code == 500
        assert "Failed to update password" in exc_info.value.detail
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_admin_transaction_summary_success(self, mock_db, mock_admin_user):
        mock_results = [
            (5, 1000.0, 200.0),
            (10, 2000.0, 200.0),
            (8, 1600.0, 200.0),
        ]

        mock_execute_result = MagicMock()
        mock_execute_result.one.side_effect = mock_results
        mock_db.execute.return_value = mock_execute_result

        with patch("app.api.routes.v1.admin.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 3, 15)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            from app.api.routes.v1.admin import get_admin_transaction_summary

            result = await get_admin_transaction_summary(db=mock_db, current_admin=mock_admin_user)

            assert isinstance(result, AdminTransactionSummary)
            assert result.overallStats.totalTransactions == 23
            assert result.overallStats.totalVolume == 4600.0
            assert len(result.monthlyStats) == 3
            assert result.monthlyStats[0].month == "Jan"
            assert result.monthlyStats[1].month == "Feb"
            assert result.monthlyStats[2].month == "Mar"

    @pytest.mark.asyncio
    async def test_get_admin_transaction_summary_no_data(self, mock_db, mock_admin_user):
        mock_execute_result = MagicMock()
        mock_execute_result.one.return_value = (0, None, None)
        mock_db.execute.return_value = mock_execute_result

        with patch("app.api.routes.v1.admin.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            from app.api.routes.v1.admin import get_admin_transaction_summary

            result = await get_admin_transaction_summary(db=mock_db, current_admin=mock_admin_user)

            assert isinstance(result, AdminTransactionSummary)
            assert result.overallStats.totalTransactions == 0
            assert result.overallStats.totalVolume == 0.0
            assert result.overallStats.overallAverage == 0.0

    @pytest.mark.asyncio
    async def test_get_balance_summary_no_data(self, mock_db, mock_admin_user):
        mock_db.scalar.return_value = 0

        mock_execute_result = MagicMock()
        mock_execute_result.one.return_value = (0, None, None)
        mock_db.execute.return_value = mock_execute_result

        with patch("app.api.routes.v1.admin.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            with patch("app.api.routes.v1.admin.calendar.monthrange", return_value=(0, 31)):
                from app.api.routes.v1.admin import get_balance_summary

                result = await get_balance_summary(db=mock_db, current_admin=mock_admin_user)

                assert isinstance(result, BalanceSummaryResponse)
                assert len(result.monthlyStats) == 1
                assert result.overallStats.totalUsers == 0
                assert result.overallStats.currentTotalBalance == 0.0

    def test_get_users_endpoint_integration(self, client):
        with (
            patch("app.api.routes.v1.admin.get_db") as mock_get_db,
            patch("app.api.routes.v1.admin.get_current_admin") as mock_get_admin,
        ):

            mock_db = AsyncMock()
            mock_admin = MagicMock()
            mock_get_db.return_value = mock_db
            mock_get_admin.return_value = mock_admin

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute.return_value = mock_result

            client.get("/api/v1/admin/users")

    def test_toggle_user_active_endpoint_integration(self, client):
        user_id = str(uuid4())

        with (
            patch("app.api.routes.v1.admin.get_db") as mock_get_db,
            patch("app.api.routes.v1.admin.get_current_admin") as mock_get_admin,
        ):

            mock_db = AsyncMock()
            mock_admin = MagicMock()
            mock_get_db.return_value = mock_db
            mock_get_admin.return_value = mock_admin

            client.patch(f"/api/v1/admin/admin/{user_id}/activate")

    @pytest.mark.asyncio
    async def test_toggle_user_active_with_invalid_uuid(self, mock_db, mock_admin_user):
        from app.api.routes.v1.admin import toggle_user_active

        valid_uuid = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await toggle_user_active(user_id=valid_uuid, db=mock_db, current_admin=mock_admin_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_transaction_summary_trend_calculations(self, mock_db, mock_admin_user):
        mock_results = [
            (5, 1000.0, 100.0),
            (10, 2000.0, 200.0),
            (8, 1200.0, 150.0),
        ]

        mock_execute_result = MagicMock()
        mock_execute_result.one.side_effect = mock_results
        mock_db.execute.return_value = mock_execute_result

        with patch("app.api.routes.v1.admin.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 3, 15)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            from app.api.routes.v1.admin import get_admin_transaction_summary

            result = await get_admin_transaction_summary(db=mock_db, current_admin=mock_admin_user)

            assert result.monthlyStats[0].trend == "up"
            assert result.monthlyStats[1].trend == "up"
            assert result.monthlyStats[2].trend == "down"

            assert result.monthlyStats[1].changePercentage == 100.0
            assert result.monthlyStats[2].changePercentage == -25.0

    @pytest.mark.asyncio
    async def test_update_user_password_exception_handling(self, mock_db, mock_admin_user, mock_regular_user):
        user_id = UUID(mock_regular_user.id)
        payload = AdminPasswordUpdateRequest(new_password="new_password")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_regular_user
        mock_db.execute.return_value = mock_result

        mock_db.commit.side_effect = Exception("Commit failed")

        from app.api.routes.v1.admin import update_user_password

        with pytest.raises(HTTPException) as exc_info:
            await update_user_password(user_id=user_id, payload=payload, db=mock_db, current_admin=mock_admin_user)

        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called_once()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


class MockTransaction:
    def __init__(self, id, amount, created_at):
        self.id = id
        self.amount = amount
        self.created_at = created_at


class MockWallet:
    def __init__(self, id, balance, created_at):
        self.id = id
        self.balance = balance
        self.created_at = created_at
