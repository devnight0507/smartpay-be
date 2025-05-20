"""
Tests for the WebSocket API.
"""

import asyncio
import json

import pytest
from httpx import AsyncClient

from app.api.websockets import WebSocketMessage, websocket_manager
from app.db.session import AsyncSession

pytestmark = pytest.mark.asyncio


class MockWebSocket:
    """Mock WebSocket class for testing."""

    def __init__(self) -> None:
        self.accepted = False
        self.closed = False
        self.close_code: int | None = None
        self.sent_messages: list[str] = []
        self.receive_queue: asyncio.Queue[str] = asyncio.Queue()

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code

    async def send_text(self, data: str) -> None:
        self.sent_messages.append(data)

    async def receive_text(self) -> str:
        return await self.receive_queue.get()

    def add_receive_message(self, message: str) -> None:
        self.receive_queue.put_nowait(message)


async def test_websocket_connection_manager() -> None:
    """Test the WebSocket connection manager."""
    # Create mock WebSockets
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    # Connect clients
    client_id1 = await websocket_manager.connect(ws1)
    client_id2 = await websocket_manager.connect(ws2)

    # Verify connections
    assert websocket_manager.get_client_count() == 2
    assert websocket_manager.is_connected(client_id1)
    assert websocket_manager.is_connected(client_id2)

    # Add to groups
    websocket_manager.add_to_group(client_id1, "group1")
    websocket_manager.add_to_group(client_id2, "group1")
    websocket_manager.add_to_group(client_id2, "group2")

    # Verify groups
    assert websocket_manager.get_group_count("group1") == 2
    assert websocket_manager.get_group_count("group2") == 1
    assert websocket_manager.get_active_groups() == ["group1", "group2"]

    # Send personal message
    message = WebSocketMessage(type="message", data={"text": "Hello"})
    await websocket_manager.send_personal_message(message, client_id1)

    # Verify message sent
    assert len(ws1.sent_messages) == 1
    assert json.loads(ws1.sent_messages[0])["type"] == "message"
    assert json.loads(ws1.sent_messages[0])["data"]["text"] == "Hello"

    # Broadcast to group
    group_message = WebSocketMessage(type="notification", data={"text": "Group notification"})
    await websocket_manager.broadcast_to_group(group_message, "group1")

    # Verify group broadcast
    assert len(ws1.sent_messages) == 2
    assert len(ws2.sent_messages) == 1
    assert json.loads(ws1.sent_messages[1])["type"] == "notification"
    assert json.loads(ws2.sent_messages[0])["type"] == "notification"

    # Broadcast to all
    broadcast_message = WebSocketMessage(type="notification", data={"text": "Broadcast"})
    await websocket_manager.broadcast(broadcast_message)

    # Verify broadcast
    assert len(ws1.sent_messages) == 3
    assert len(ws2.sent_messages) == 2

    # Disconnect client
    websocket_manager.disconnect(client_id1)

    # Verify disconnection
    assert websocket_manager.get_client_count() == 1
    assert not websocket_manager.is_connected(client_id1)
    assert websocket_manager.get_group_count("group1") == 1


async def test_websocket_api(client: AsyncClient, db_session: AsyncSession) -> None:
    """Test WebSocket endpoints.

    Note: This is a high-level HTTP test for the broadcast endpoint.
    Testing actual WebSocket connections requires a more complex
    test setup with WebSocket client protocol.
    """
    # Test stats endpoint - should require authentication
    response = await client.get("/api/v1/ws/stats")
    assert response.status_code == 401
