# from app.api.routes.v1.endpoints.websockets.notifications import active_connections
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.models import Notification


async def notify_user(
    db: AsyncSession,
    user_id: str,
    title: str,
    message: str,
    type: str = "system",
    transaction_id: Optional[str] = None,
    amount: Optional[float] = None,
) -> dict:  # type: ignore
    """
    Create a notification for a user and return the structured response.
    """
    extra_data = (
        {
            "transactionId": transaction_id,
            "amount": amount,
        }
        if transaction_id or amount
        else None
    )

    notification = Notification(
        id=str(uuid4()),
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        is_read=False,
        created_at=datetime.utcnow(),
        extra_data=extra_data,
    )

    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "is_read": notification.is_read,
        "created_at": notification.created_at,
        "extra_data": notification.extra_data,
    }
