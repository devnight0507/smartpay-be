"""
WebSocket connection manager and utilities.
"""

import json
from asyncio import Queue
from typing import Any, Dict, List, Optional, Set, TypeVar, cast
from uuid import UUID, uuid4

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, field_validator

T = TypeVar("T")


class WebSocketMessage(BaseModel):
    """
    Base model for WebSocket messages.
    """

    type: str
    data: Dict[str, Any]
    message_id: str = str(uuid4())

    @field_validator("type")
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        """Validates message type."""
        allowed_types = {"message", "notification", "event", "error"}
        if v not in allowed_types:
            raise ValueError(f"Invalid message type. Must be one of {allowed_types}")
        return v


class ConnectionManager:
    """
    WebSocket connection manager to handle multiple client connections.

    Features:
    - Tracks active connections
    - Supports client identification
    - Handles connection groups
    - Provides broadcast capabilities
    - Integrates with logging
    """

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: Dict[UUID, WebSocket] = {}
        self.client_queues: Dict[UUID, Queue] = {}
        self.connection_groups: Dict[str, Set[UUID]] = {}

    async def connect(self, websocket: WebSocket, client_id: Optional[UUID] = None) -> UUID:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept
            client_id: Optional client identifier

        Returns:
            The client ID (provided or generated)
        """
        await websocket.accept()

        # Generate a new client ID if not provided
        if client_id is None:
            client_id = uuid4()

        # Store the connection
        self.active_connections[client_id] = websocket
        self.client_queues[client_id] = Queue()

        logger.info("WebSocket connection established", extra={"client_id": str(client_id)})
        return client_id

    def disconnect(self, client_id: UUID) -> None:
        """
        Handle a disconnected client.

        Args:
            client_id: The client's ID
        """
        # Remove from active connections
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from queues
        if client_id in self.client_queues:
            del self.client_queues[client_id]

        # Remove from all groups
        for group in self.connection_groups.values():
            if client_id in group:
                group.remove(client_id)

        logger.info("WebSocket connection closed", extra={"client_id": str(client_id)})

    def add_to_group(self, client_id: UUID, group_name: str) -> None:
        """
        Add a client to a connection group.

        Args:
            client_id: The client's ID
            group_name: The group to add the client to
        """
        if client_id not in self.active_connections:
            return

        if group_name not in self.connection_groups:
            self.connection_groups[group_name] = set()

        self.connection_groups[group_name].add(client_id)
        logger.debug("Client added to group", extra={"client_id": str(client_id), "group": group_name})

    def remove_from_group(self, client_id: UUID, group_name: str) -> None:
        """
        Remove a client from a connection group.

        Args:
            client_id: The client's ID
            group_name: The group to remove the client from
        """
        if group_name in self.connection_groups and client_id in self.connection_groups[group_name]:
            self.connection_groups[group_name].remove(client_id)
            logger.debug("Client removed from group", extra={"client_id": str(client_id), "group": group_name})

    async def send_personal_message(self, message: WebSocketMessage, client_id: UUID) -> bool:
        """
        Send a message to a specific client.

        Args:
            message: The message to send
            client_id: The recipient client's ID

        Returns:
            True if the message was sent successfully, False otherwise
        """
        if client_id not in self.active_connections:
            logger.warning(
                "Failed to send personal message: client not connected", extra={"client_id": str(client_id)}
            )
            return False

        try:
            websocket = self.active_connections[client_id]
            await websocket.send_text(message.model_dump_json())
            logger.debug("Personal message sent", extra={"client_id": str(client_id), "message_type": message.type})
            return True
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}", extra={"client_id": str(client_id)})
            return False

    async def broadcast(self, message: WebSocketMessage) -> None:
        """
        Broadcast a message to all connected clients.

        Args:
            message: The message to broadcast
        """
        disconnected_clients = []

        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message.model_dump_json())
            except Exception as e:
                logger.error(f"Error during broadcast: {str(e)}", extra={"client_id": str(client_id)})
                disconnected_clients.append(client_id)

        # Clean up any disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

        logger.debug(
            f"Message broadcast to {len(self.active_connections)} clients", extra={"message_type": message.type}
        )

    async def broadcast_to_group(self, message: WebSocketMessage, group_name: str) -> None:
        """
        Broadcast a message to a specific group of clients.

        Args:
            message: The message to broadcast
            group_name: The group to send to
        """
        if group_name not in self.connection_groups:
            logger.warning(f"Group not found for broadcast: {group_name}")
            return

        disconnected_clients = []

        for client_id in self.connection_groups[group_name]:
            if client_id in self.active_connections:
                try:
                    websocket = self.active_connections[client_id]
                    await websocket.send_text(message.model_dump_json())
                except Exception as e:
                    logger.error(
                        f"Error during group broadcast: {str(e)}",
                        extra={"client_id": str(client_id), "group": group_name},
                    )
                    disconnected_clients.append(client_id)

        # Clean up any disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

        logger.debug(
            "Message broadcast to group",
            extra={
                "group": group_name,
                "client_count": len(self.connection_groups[group_name]),
                "message_type": message.type,
            },
        )

    async def receive_text(self, client_id: UUID) -> Dict[str, Any]:
        """
        Receive a text message from a client.

        Args:
            client_id: The client's ID

        Returns:
            The parsed JSON message

        Raises:
            WebSocketDisconnect: If the client disconnects
        """
        if client_id not in self.active_connections:
            raise WebSocketDisconnect(code=1001, reason="Client not connected")

        websocket = self.active_connections[client_id]

        try:
            data = await websocket.receive_text()
            parsed_data = json.loads(data)
            return cast(Dict[str, Any], parsed_data)
        except WebSocketDisconnect:
            self.disconnect(client_id)
            raise
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received", extra={"client_id": str(client_id)})
            return {"type": "error", "data": {"message": "Invalid JSON format"}}
        except Exception as e:
            logger.error(f"Error receiving websocket message: {str(e)}", extra={"client_id": str(client_id)})
            return {"type": "error", "data": {"message": "Error processing message"}}

    def get_client_count(self) -> int:
        """
        Get the number of active connections.

        Returns:
            The number of active client connections
        """
        return len(self.active_connections)

    def get_group_count(self, group_name: str) -> int:
        """
        Get the number of clients in a group.

        Args:
            group_name: The group name

        Returns:
            The number of clients in the group
        """
        if group_name not in self.connection_groups:
            return 0
        return len(self.connection_groups[group_name])

    def get_active_groups(self) -> List[str]:
        """
        Get a list of all active groups.

        Returns:
            A list of group names
        """
        return list(self.connection_groups.keys())

    def is_connected(self, client_id: UUID) -> bool:
        """
        Check if a client is connected.

        Args:
            client_id: The client's ID

        Returns:
            True if the client is connected, False otherwise
        """
        return client_id in self.active_connections


# Singleton instance of the connection manager
websocket_manager = ConnectionManager()
