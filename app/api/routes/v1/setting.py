from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.dependencies import get_current_active_user
from app.db.models.models import User, UserNotificationSetting
from app.db.session import get_db
from app.schemas.schemas import NotificationSettings, NotificationSettingsUpdate

router = APIRouter()


@router.get("/get", response_model=list[NotificationSettings])
async def get_user_notification_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[NotificationSettings]:
    query = select(UserNotificationSetting).where(UserNotificationSetting.user_id == current_user.id)
    result = await db.execute(query)
    settings = result.scalars().all()

    if not settings:
        settings = UserNotificationSetting(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings[0]


@router.patch("/update", response_model=NotificationSettings)
async def update_user_notification_settings(
    update_data: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationSettings:
    query = select(UserNotificationSetting).where(UserNotificationSetting.user_id == current_user.id)
    result = await db.execute(query)
    settings = result.scalars().first()

    if not settings:
        settings = UserNotificationSetting(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(settings, field, value)

    await db.commit()
    return settings
