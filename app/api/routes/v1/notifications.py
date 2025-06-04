from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_verified_user
from app.api.responses import default_error_responses
from app.db.models.models import Notification, User
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=List[dict], summary="Get current user's notifications")
async def get_my_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> List[dict]:
    query = (
        select(Notification)
        .where(Notification.user_id == str(current_user.id))
        .order_by(Notification.created_at.desc())
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "read": n.is_read,
            "timestamp": n.created_at,
            "extra_data": n.extra_data,  # future use
        }
        for n in notifications
    ]


@router.post("/{notification_id}/read", summary="Mark notification as read", responses=default_error_responses)
async def mark_notification_read(
    notification_id: str = Path(..., description="Notification UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == str(current_user.id),
    )
    result = await db.execute(query)
    notification = result.scalars().first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True  # type: ignore
    await db.commit()
    await db.refresh(notification)

    return {
        "message": "Notification marked as read",
        "id": notification.id,
        "read": notification.is_read,
    }


@router.post("/mark-all-read", summary="Mark all notifications as read")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    query = select(Notification).where(Notification.user_id == str(current_user.id), Notification.is_read.is_(False))
    result = await db.execute(query)
    notifications = result.scalars().all()

    for notif in notifications:
        notif.is_read = True  # type: ignore

    await db.commit()

    return {"message": f"{len(notifications)} notification(s) marked as read"}


@router.delete("/{notification_id}", summary="Delete a notification by ID", responses=default_error_responses)
async def delete_notification(
    notification_id: str = Path(..., description="Notification UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == str(current_user.id),
    )
    result = await db.execute(query)
    notification = result.scalars().first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Delete the notification
    await db.delete(notification)
    await db.commit()

    return {
        "message": "Notification deleted successfully",
        "id": notification.id,
    }
