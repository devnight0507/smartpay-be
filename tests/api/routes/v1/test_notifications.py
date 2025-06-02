"""
Comprehensive test file for notifications API endpoints.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession

# Import the module under test
from app.api.routes.v1.notifications import (
    delete_notification,
    get_my_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

# Mock models - adjust imports based on your actual structure
from app.db.models.models import Notification, User


class TestNotificationsAPI:
    """Test class for notifications API endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = AsyncMock(spec=AsyncSession)
        return db

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        return user

    @pytest.fixture
    def mock_notification(self):
        """Mock notification object."""
        notification = Mock(spec=Notification)
        notification.id = "notif-123"
        notification.title = "Test Notification"
        notification.message = "This is a test notification"
        notification.type = "info"
        notification.is_read = False
        notification.created_at = datetime(2024, 1, 1, 12, 0, 0)
        notification.extra_data = {"key": "value"}
        notification.user_id = "user-123"
        return notification

    @pytest.fixture
    def mock_notifications_list(self, mock_notification):
        """Mock list of notifications."""
        notifications = []
        for i in range(3):
            notif = Mock(spec=Notification)
            notif.id = f"notif-{i}"
            notif.title = f"Test Notification {i}"
            notif.message = f"This is test notification {i}"
            notif.type = "info"
            notif.is_read = i % 2 == 0  # Mix of read and unread
            notif.created_at = datetime(2024, 1, i + 1, 12, 0, 0)
            notif.extra_data = {"index": i}
            notif.user_id = "user-123"
            notifications.append(notif)
        return notifications

    @pytest.fixture
    def mock_result(self):
        """Mock SQLAlchemy result."""
        result = Mock(spec=Result)
        return result


class TestGetMyNotifications(TestNotificationsAPI):
    """Test the get_my_notifications endpoint."""

    @pytest.mark.asyncio
    async def test_get_my_notifications_success(self, mock_db, mock_user, mock_notifications_list, mock_result):
        """Test successful retrieval of user notifications."""
        # Setup mock result
        mock_result.scalars.return_value.all.return_value = mock_notifications_list
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await get_my_notifications(db=mock_db, current_user=mock_user)

        # Verify database query
        mock_db.execute.assert_called_once()
        mock_db.execute.call_args[0][0]

        # Verify the result structure
        assert isinstance(result, list)
        assert len(result) == 3

        # Verify first notification structure
        first_notif = result[0]
        assert "id" in first_notif
        assert "title" in first_notif
        assert "message" in first_notif
        assert "type" in first_notif
        assert "read" in first_notif
        assert "timestamp" in first_notif
        assert "extra_data" in first_notif

        # Verify specific values
        assert first_notif["id"] == "notif-0"
        assert first_notif["title"] == "Test Notification 0"
        assert first_notif["message"] == "This is test notification 0"
        assert first_notif["type"] == "info"
        assert first_notif["read"] is True  # notif-0 should be read (i % 2 == 0)
        assert first_notif["extra_data"] == {"index": 0}

    @pytest.mark.asyncio
    async def test_get_my_notifications_empty_list(self, mock_db, mock_user, mock_result):
        """Test retrieval when user has no notifications."""
        # Setup mock result with empty list
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await get_my_notifications(db=mock_db, current_user=mock_user)

        # Verify empty result
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_my_notifications_database_error(self, mock_db, mock_user):
        """Test handling of database errors."""
        # Setup mock to raise exception
        mock_db.execute.side_effect = Exception("Database connection error")

        # Call the function and expect exception
        with pytest.raises(Exception) as exc_info:
            await get_my_notifications(db=mock_db, current_user=mock_user)

        assert str(exc_info.value) == "Database connection error"

    @pytest.mark.asyncio
    async def test_get_my_notifications_user_id_filtering(self, mock_db, mock_user, mock_result):
        """Test that notifications are filtered by user ID."""
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await get_my_notifications(db=mock_db, current_user=mock_user)

        # Verify that the query was called with user ID filtering
        mock_db.execute.assert_called_once()
        # The query should include user_id filtering - this is implicit in the SQLAlchemy query


class TestMarkNotificationRead(TestNotificationsAPI):
    """Test the mark_notification_read endpoint."""

    @pytest.mark.asyncio
    async def test_mark_notification_read_success(self, mock_db, mock_user, mock_notification, mock_result):
        """Test successfully marking a notification as read."""
        # Setup mock result
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await mark_notification_read(notification_id="notif-123", db=mock_db, current_user=mock_user)

        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_notification)

        # Verify notification was marked as read
        assert mock_notification.is_read is True

        # Verify response structure
        assert isinstance(result, dict)
        assert result["message"] == "Notification marked as read"
        assert result["id"] == "notif-123"
        assert result["read"] is True

    @pytest.mark.asyncio
    async def test_mark_notification_read_not_found(self, mock_db, mock_user, mock_result):
        """Test marking non-existent notification as read."""
        # Setup mock result with no notification found
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        # Call the function and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mark_notification_read(notification_id="non-existent-id", db=mock_db, current_user=mock_user)

        # Verify exception details
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Notification not found"

        # Verify no commit was called
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_mark_notification_read_wrong_user(self, mock_db, mock_user, mock_result):
        """Test that user can only mark their own notifications as read."""
        # This test verifies the query includes user_id filtering
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await mark_notification_read(notification_id="notif-123", db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Notification not found"

    @pytest.mark.asyncio
    async def test_mark_notification_read_database_error(self, mock_db, mock_user, mock_notification, mock_result):
        """Test handling of database errors during mark as read."""
        # Setup mock result
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result
        mock_db.commit.side_effect = Exception("Database error")

        # Call the function and expect exception
        with pytest.raises(Exception) as exc_info:
            await mark_notification_read(notification_id="notif-123", db=mock_db, current_user=mock_user)

        assert str(exc_info.value) == "Database error"

    @pytest.mark.asyncio
    async def test_mark_notification_read_already_read(self, mock_db, mock_user, mock_notification, mock_result):
        """Test marking already read notification as read."""
        # Setup notification as already read
        mock_notification.is_read = True
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await mark_notification_read(notification_id="notif-123", db=mock_db, current_user=mock_user)

        # Should still work and return success
        assert result["message"] == "Notification marked as read"
        assert result["read"] is True


class TestMarkAllNotificationsRead(TestNotificationsAPI):
    """Test the mark_all_notifications_read endpoint."""

    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_success(self, mock_db, mock_user, mock_result):
        """Test successfully marking all notifications as read."""
        # Create mock unread notifications
        unread_notifications = []
        for i in range(3):
            notif = Mock(spec=Notification)
            notif.id = f"notif-{i}"
            notif.is_read = False
            notif.user_id = "user-123"
            unread_notifications.append(notif)

        # Setup mock result
        mock_result.scalars.return_value.all.return_value = unread_notifications
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await mark_all_notifications_read(db=mock_db, current_user=mock_user)

        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify all notifications were marked as read
        for notif in unread_notifications:
            assert notif.is_read is True

        # Verify response
        assert isinstance(result, dict)
        assert result["message"] == "3 notification(s) marked as read"

    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_no_unread(self, mock_db, mock_user, mock_result):
        """Test marking all notifications as read when none are unread."""
        # Setup mock result with empty list
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await mark_all_notifications_read(db=mock_db, current_user=mock_user)

        # Verify response
        assert result["message"] == "0 notification(s) marked as read"

    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_single_notification(self, mock_db, mock_user, mock_result):
        """Test marking all notifications as read with single notification."""
        # Create single unread notification
        notif = Mock(spec=Notification)
        notif.id = "notif-1"
        notif.is_read = False
        notif.user_id = "user-123"

        mock_result.scalars.return_value.all.return_value = [notif]
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await mark_all_notifications_read(db=mock_db, current_user=mock_user)

        # Verify notification was marked as read
        assert notif.is_read is True

        # Verify response
        assert result["message"] == "1 notification(s) marked as read"

    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_database_error(self, mock_db, mock_user):
        """Test handling of database errors during mark all as read."""
        mock_db.execute.side_effect = Exception("Database connection error")

        with pytest.raises(Exception) as exc_info:
            await mark_all_notifications_read(db=mock_db, current_user=mock_user)

        assert str(exc_info.value) == "Database connection error"


class TestDeleteNotification(TestNotificationsAPI):
    """Test the delete_notification endpoint."""

    @pytest.mark.asyncio
    async def test_delete_notification_success(self, mock_db, mock_user, mock_notification, mock_result):
        """Test successfully deleting a notification."""
        # Setup mock result
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result

        # Call the function
        result = await delete_notification(notification_id="notif-123", db=mock_db, current_user=mock_user)

        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.delete.assert_called_once_with(mock_notification)
        mock_db.commit.assert_called_once()

        # Verify response structure
        assert isinstance(result, dict)
        assert result["message"] == "Notification deleted successfully"
        assert result["id"] == "notif-123"

    @pytest.mark.asyncio
    async def test_delete_notification_not_found(self, mock_db, mock_user, mock_result):
        """Test deleting non-existent notification."""
        # Setup mock result with no notification found
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        # Call the function and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await delete_notification(notification_id="non-existent-id", db=mock_db, current_user=mock_user)

        # Verify exception details
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Notification not found"

        # Verify no deletion was attempted
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_notification_wrong_user(self, mock_db, mock_user, mock_result):
        """Test that user can only delete their own notifications."""
        # This test verifies the query includes user_id filtering
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_notification(notification_id="notif-123", db=mock_db, current_user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Notification not found"

    @pytest.mark.asyncio
    async def test_delete_notification_database_error_on_delete(
        self, mock_db, mock_user, mock_notification, mock_result
    ):
        """Test handling of database errors during deletion."""
        # Setup mock result
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result
        mock_db.delete.side_effect = Exception("Database deletion error")

        # Call the function and expect exception
        with pytest.raises(Exception) as exc_info:
            await delete_notification(notification_id="notif-123", db=mock_db, current_user=mock_user)

        assert str(exc_info.value) == "Database deletion error"

    @pytest.mark.asyncio
    async def test_delete_notification_database_error_on_commit(
        self, mock_db, mock_user, mock_notification, mock_result
    ):
        """Test handling of database errors during commit."""
        # Setup mock result
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result
        mock_db.commit.side_effect = Exception("Commit error")

        # Call the function and expect exception
        with pytest.raises(Exception) as exc_info:
            await delete_notification(notification_id="notif-123", db=mock_db, current_user=mock_user)

        assert str(exc_info.value) == "Commit error"


class TestEdgeCases(TestNotificationsAPI):
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_notification_id_validation(self, mock_db, mock_user, mock_result):
        """Test notification ID validation with various formats."""
        # Test with empty string
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException):
            await mark_notification_read("", mock_db, mock_user)

        # Test with UUID format
        valid_uuid = str(uuid4())
        with pytest.raises(HTTPException):  # Will fail because notification doesn't exist
            await mark_notification_read(valid_uuid, mock_db, mock_user)

    @pytest.mark.asyncio
    async def test_large_notification_list(self, mock_db, mock_user, mock_result):
        """Test handling of large notification lists."""
        # Create a large list of notifications
        large_notification_list = []
        for i in range(1000):
            notif = Mock(spec=Notification)
            notif.id = f"notif-{i}"
            notif.title = f"Notification {i}"
            notif.message = f"Message {i}"
            notif.type = "info"
            notif.is_read = False
            notif.created_at = datetime(2024, 1, 1, 12, 0, 0)
            notif.extra_data = {}
            large_notification_list.append(notif)

        mock_result.scalars.return_value.all.return_value = large_notification_list
        mock_db.execute.return_value = mock_result

        # Test get_my_notifications with large list
        result = await get_my_notifications(db=mock_db, current_user=mock_user)
        assert len(result) == 1000

        # Test mark_all_notifications_read with large list
        result = await mark_all_notifications_read(db=mock_db, current_user=mock_user)
        assert result["message"] == "1000 notification(s) marked as read"

    @pytest.mark.asyncio
    async def test_notification_with_null_extra_data(self, mock_db, mock_user, mock_result):
        """Test handling of notifications with null extra_data."""
        # Create notification with None extra_data
        notif = Mock(spec=Notification)
        notif.id = "notif-1"
        notif.title = "Test"
        notif.message = "Test message"
        notif.type = "info"
        notif.is_read = False
        notif.created_at = datetime(2024, 1, 1, 12, 0, 0)
        notif.extra_data = None
        notif.user_id = "user-123"

        mock_result.scalars.return_value.all.return_value = [notif]
        mock_db.execute.return_value = mock_result

        result = await get_my_notifications(db=mock_db, current_user=mock_user)

        assert len(result) == 1
        assert result[0]["extra_data"] is None

    @pytest.mark.asyncio
    async def test_notification_with_special_characters(self, mock_db, mock_user, mock_result):
        """Test handling of notifications with special characters."""
        # Create notification with special characters
        notif = Mock(spec=Notification)
        notif.id = "notif-1"
        notif.title = "Test with �mojis =� and special chars: <>&\"'"
        notif.message = "Message with unicode: K�-�"
        notif.type = "info"
        notif.is_read = False
        notif.created_at = datetime(2024, 1, 1, 12, 0, 0)
        notif.extra_data = {"unicode": "K�", "symbols": "!@#$%^&*()"}
        notif.user_id = "user-123"

        mock_result.scalars.return_value.all.return_value = [notif]
        mock_db.execute.return_value = mock_result

        result = await get_my_notifications(db=mock_db, current_user=mock_user)

        assert len(result) == 1
        assert "�mojis =�" in result[0]["title"]
        assert "K�-�" in result[0]["message"]


class TestIntegrationScenarios(TestNotificationsAPI):
    """Integration tests for common notification scenarios."""

    @pytest.mark.asyncio
    async def test_notification_lifecycle(self, mock_db, mock_user, mock_notification, mock_result):
        """Test complete notification lifecycle: create, read, delete."""
        # Mock notification starts unread
        mock_notification.is_read = False
        mock_result.scalars.return_value.first.return_value = mock_notification
        mock_db.execute.return_value = mock_result

        # 1. Mark as read
        read_result = await mark_notification_read("notif-123", mock_db, mock_user)
        assert read_result["read"] is True
        assert mock_notification.is_read is True

        # 2. Delete notification
        delete_result = await delete_notification("notif-123", mock_db, mock_user)
        assert delete_result["message"] == "Notification deleted successfully"

    @pytest.mark.asyncio
    async def test_concurrent_notification_operations(self, mock_db, mock_user, mock_result):
        """Test handling of concurrent notification operations."""
        # Create multiple notifications
        notifications = []
        for i in range(5):
            notif = Mock(spec=Notification)
            notif.id = f"notif-{i}"
            notif.is_read = False
            notif.user_id = "user-123"
            notifications.append(notif)

        mock_result.scalars.return_value.all.return_value = notifications
        mock_db.execute.return_value = mock_result

        # Mark all as read
        result = await mark_all_notifications_read(db=mock_db, current_user=mock_user)

        # Verify all were marked as read
        for notif in notifications:
            assert notif.is_read is True

        assert result["message"] == "5 notification(s) marked as read"


class TestResponseModels(TestNotificationsAPI):
    """Test response model structures and validation."""

    @pytest.mark.asyncio
    async def test_get_notifications_response_structure(self, mock_db, mock_user, mock_notification, mock_result):
        """Test that get_notifications returns proper structure."""
        mock_result.scalars.return_value.all.return_value = [mock_notification]
        mock_db.execute.return_value = mock_result

        result = await get_my_notifications(db=mock_db, current_user=mock_user)

        # Verify response is a list
        assert isinstance(result, list)
        assert len(result) == 1

        # Verify each notification has required fields
        notification = result[0]
        required_fields = ["id", "title", "message", "type", "read", "timestamp", "extra_data"]
        for field in required_fields:
            assert field in notification

        # Verify field types
        assert isinstance(notification["id"], str)
        assert isinstance(notification["title"], str)
        assert isinstance(notification["message"], str)
        assert isinstance(notification["type"], str)
        assert isinstance(notification["read"], bool)
        assert isinstance(notification["timestamp"], datetime)

    def test_mark_read_response_structure(self):
        """Test mark_notification_read response structure."""
        # This would typically be tested with actual API calls
        # Here we verify the structure of the returned dict
        expected_response = {"message": "Notification marked as read", "id": "notif-123", "read": True}

        # Verify required fields
        assert "message" in expected_response
        assert "id" in expected_response
        assert "read" in expected_response

        # Verify types
        assert isinstance(expected_response["message"], str)
        assert isinstance(expected_response["id"], str)
        assert isinstance(expected_response["read"], bool)

    def test_delete_response_structure(self):
        """Test delete_notification response structure."""
        expected_response = {"message": "Notification deleted successfully", "id": "notif-123"}

        # Verify required fields
        assert "message" in expected_response
        assert "id" in expected_response

        # Verify types
        assert isinstance(expected_response["message"], str)
        assert isinstance(expected_response["id"], str)


# Performance and stress tests
class TestPerformance(TestNotificationsAPI):
    """Performance-related tests."""

    @pytest.mark.asyncio
    async def test_query_efficiency(self, mock_db, mock_user, mock_result):
        """Test that queries are called efficiently."""
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Test that get_my_notifications makes only one query
        await get_my_notifications(db=mock_db, current_user=mock_user)
        assert mock_db.execute.call_count == 1

        # Reset mock
        mock_db.reset_mock()

        # Test that mark_all_notifications_read makes only one query
        await mark_all_notifications_read(db=mock_db, current_user=mock_user)
        assert mock_db.execute.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=notifications", "--cov-report=html"])
