import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect

from app.api.originalwebsockets import ConnectionManager, WebSocketMessage


@pytest.mark.asyncio
async def test_websocket_message_validation_pass():
    msg = WebSocketMessage(type="message", data={"text": "hi"})
    assert msg.type == "message"
    assert isinstance(msg.message_id, str)


def test_websocket_message_invalid_type():
    with pytest.raises(ValueError):
        WebSocketMessage(type="invalid", data={})


@pytest.mark.asyncio
async def test_connection_lifecycle():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    client_id = await manager.connect(mock_ws)
    assert manager.is_connected(client_id)
    assert manager.get_client_count() == 1

    manager.disconnect(client_id)
    assert not manager.is_connected(client_id)
    assert manager.get_client_count() == 0


def test_add_and_remove_from_group():
    manager = ConnectionManager()
    cid = uuid4()
    manager.active_connections[cid] = AsyncMock()

    manager.add_to_group(cid, "room1")
    assert manager.get_group_count("room1") == 1

    manager.remove_from_group(cid, "room1")
    assert manager.get_group_count("room1") == 0


@pytest.mark.asyncio
async def test_send_personal_message_success():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    client_id = await manager.connect(mock_ws)

    message = WebSocketMessage(type="message", data={"text": "hi"})
    sent = await manager.send_personal_message(message, client_id)
    assert sent
    mock_ws.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_send_personal_message_failure():
    manager = ConnectionManager()
    message = WebSocketMessage(type="message", data={})
    sent = await manager.send_personal_message(message, uuid4())
    assert not sent


@pytest.mark.asyncio
async def test_broadcast_handles_disconnect():
    manager = ConnectionManager()
    cid1, cid2 = uuid4(), uuid4()

    # First succeeds, second raises error
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws2.send_text.side_effect = Exception("fail")

    manager.active_connections[cid1] = ws1
    manager.active_connections[cid2] = ws2

    message = WebSocketMessage(type="message", data={"text": "hello"})
    await manager.broadcast(message)

    assert manager.is_connected(cid1)
    assert not manager.is_connected(cid2)  # disconnected due to error


@pytest.mark.asyncio
async def test_broadcast_to_group():
    manager = ConnectionManager()
    cid = uuid4()
    ws = AsyncMock()

    manager.active_connections[cid] = ws
    manager.add_to_group(cid, "roomX")

    msg = WebSocketMessage(type="message", data={"x": 1})
    await manager.broadcast_to_group(msg, "roomX")
    ws.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_receive_text_valid_json():
    manager = ConnectionManager()
    ws = AsyncMock()
    ws.receive_text.return_value = json.dumps({"type": "message", "data": {"ok": 1}})
    cid = await manager.connect(ws)

    result = await manager.receive_text(cid)
    assert result["type"] == "message"


@pytest.mark.asyncio
async def test_receive_text_invalid_json():
    manager = ConnectionManager()
    ws = AsyncMock()
    ws.receive_text.return_value = "not_json"
    cid = await manager.connect(ws)

    result = await manager.receive_text(cid)
    assert result["type"] == "error"


@pytest.mark.asyncio
async def test_receive_text_disconnect():
    manager = ConnectionManager()
    ws = AsyncMock()
    ws.receive_text.side_effect = WebSocketDisconnect()
    cid = await manager.connect(ws)

    with pytest.raises(WebSocketDisconnect):
        await manager.receive_text(cid)


def test_group_utilities():
    manager = ConnectionManager()
    cid = uuid4()
    manager.active_connections[cid] = AsyncMock()
    manager.add_to_group(cid, "roomA")

    assert manager.get_group_count("roomA") == 1
    assert "roomA" in manager.get_active_groups()
    assert manager.is_connected(cid)
