"""
WebSocket endpoints for real-time notifications.
"""

from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from loguru import logger

from app.api.dependencies import get_current_user
from app.api.websockets import WebSocketMessage, websocket_manager
from app.core.metrics import BUSINESS_EVENTS

router = APIRouter()


@router.websocket("/connect")
async def websocket_notifications(
    websocket: WebSocket, user_id: Optional[str] = None, authorization: Optional[str] = Header(None)
) -> None:
    """
    WebSocket endpoint for real-time notifications.

    Allows clients to subscribe to real-time updates, including:
    - System notifications
    - User-specific updates
    - Topic-based subscriptions
    """
    client_id = None

    try:
        # Authenticate connection if needed
        if authorization:
            try:
                # Simple authentication - in production, proper auth would be implemented
                if not authorization.startswith("Bearer "):
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

                # Extract the user ID if not explicitly provided
                if not user_id:
                    # This is a simplified example
                    user_id = "user123"  # Would be extracted from token

            except Exception as e:
                logger.error(f"WebSocket authentication error: {str(e)}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        # Accept connection and get client ID
        client_id = await websocket_manager.connect(websocket)

        # Add to user-specific group if user_id provided
        if user_id:
            user_group = f"user_{user_id}"
            websocket_manager.add_to_group(client_id, user_group)

            # Send welcome message
            welcome_msg = WebSocketMessage(
                type="notification", data={"message": "Connected to notification service", "user_id": user_id}
            )
            await websocket_manager.send_personal_message(welcome_msg, client_id)

        # Main message loop
        while True:
            # Wait for messages from the client
            data = await websocket_manager.receive_text(client_id)

            try:
                # Process subscription requests
                if data.get("type") == "subscribe":
                    topic = data.get("data", {}).get("topic")
                    if topic:
                        websocket_manager.add_to_group(client_id, f"topic_{topic}")

                        # Track subscription
                        BUSINESS_EVENTS.labels(event_type="websocket_subscription").inc()

                        await websocket_manager.send_personal_message(
                            WebSocketMessage(
                                type="notification", data={"message": f"Subscribed to {topic}", "topic": topic}
                            ),
                            client_id,
                        )

                # Process unsubscribe requests
                elif data.get("type") == "unsubscribe":
                    topic = data.get("data", {}).get("topic")
                    if topic:
                        websocket_manager.remove_from_group(client_id, f"topic_{topic}")
                        await websocket_manager.send_personal_message(
                            WebSocketMessage(
                                type="notification", data={"message": f"Unsubscribed from {topic}", "topic": topic}
                            ),
                            client_id,
                        )

                # Echo back other messages (demo purpose)
                elif data.get("type") == "message":
                    await websocket_manager.send_personal_message(
                        WebSocketMessage(type="message", data={"echo": data.get("data", {})}), client_id
                    )
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")
                await websocket_manager.send_personal_message(
                    WebSocketMessage(type="error", data={"message": "Error processing your request"}), client_id
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", extra={"client_id": str(client_id) if client_id else None})
    except Exception as e:
        logger.exception(f"WebSocket error: {str(e)}")
    finally:
        # Cleanup on disconnect
        if client_id:
            websocket_manager.disconnect(client_id)


@router.post("/broadcast", response_model=Dict[str, Any])
async def broadcast_notification(
    message: Dict[str, Any],
    topic: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user()),
) -> Dict[str, Any]:
    """
    Broadcast a notification to WebSocket clients.

    Args:
        message: The message to broadcast
        topic: Optional topic to target specific subscribers
        user_id: Optional user ID to target a specific user

    Returns:
        Status of the broadcast operation
    """
    # Validate user has permission to broadcast (admin check example)
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to broadcast messages"
        )

    websocket_message = WebSocketMessage(type="notification", data=message)

    # Broadcast to specific user
    if user_id:
        user_group = f"user_{user_id}"
        await websocket_manager.broadcast_to_group(websocket_message, user_group)
        return {
            "success": True,
            "message": f"Message broadcast to user {user_id}",
            "recipients": websocket_manager.get_group_count(user_group),
        }

    # Broadcast to topic subscribers
    elif topic:
        topic_group = f"topic_{topic}"
        await websocket_manager.broadcast_to_group(websocket_message, topic_group)
        return {
            "success": True,
            "message": f"Message broadcast to topic {topic}",
            "recipients": websocket_manager.get_group_count(topic_group),
        }

    # Broadcast to all clients
    else:
        await websocket_manager.broadcast(websocket_message)
        return {
            "success": True,
            "message": "Message broadcast to all clients",
            "recipients": websocket_manager.get_client_count(),
        }


@router.get("/stats", response_model=Dict[str, Any])
async def websocket_stats(current_user: Dict[str, Any] = Depends(get_current_user())) -> Dict[str, Any]:
    """
    Get statistics about active WebSocket connections.

    Returns:
        Statistics about active connections and groups
    """
    # Validate user has permission (admin check example)
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to view WebSocket statistics"
        )

    # Get active groups and their counts
    groups = websocket_manager.get_active_groups()
    group_stats = {group: websocket_manager.get_group_count(group) for group in groups}

    return {"total_connections": websocket_manager.get_client_count(), "groups": group_stats}
