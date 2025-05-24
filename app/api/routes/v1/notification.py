# notification.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_active_user
from app.db.models.models import Notification, User
from app.db.session import get_db
from app.schemas.schemas import NotificationInDBBase

router = APIRouter()


@router.get("/notifications", response_model=list[NotificationInDBBase])
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[NotificationInDBBase]:
    query = select(Notification).where(Notification.user_id == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()[0]


@router.patch("/notifications/{notification_id}/read", response_model=NotificationInDBBase)
async def mark_notification_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationInDBBase:
    query = select(Notification).where(
        Notification.id == str(notification_id), Notification.user_id == current_user.id
    )
    result = await db.execute(query)
    notification = result.scalars().first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True  # type: ignore
    await db.commit()
    return notification
