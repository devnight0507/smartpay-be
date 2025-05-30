from fastapi import APIRouter, WebSocket

from app.utils.connection_manager import manager

router = APIRouter()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except Exception:
        manager.disconnect(user_id)
