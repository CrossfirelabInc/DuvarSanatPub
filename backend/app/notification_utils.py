"""Notification helper utilities."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    message: str | None = None,
    link: str | None = None,
) -> Notification:
    """Insert a notification row for the given user.

    Args:
        db: Async database session.
        user_id: Target user to notify.
        type: Notification type (e.g. 'badge_earned', 'new_photo', 'claim_approved').
        title: Short notification title.
        message: Optional longer message body.
        link: Optional URL/path the notification links to.

    Returns:
        The created Notification instance.
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link=link,
    )
    db.add(notification)
    return notification
