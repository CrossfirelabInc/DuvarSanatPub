"""Admin settings endpoints: feature toggles and site configuration."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import SiteSetting, User

router = APIRouter(tags=["admin-settings"])

FEATURE_TOGGLES = [
    "dm_enabled",
    "tours_enabled",
    "ai_naming_enabled",
    "challenges_enabled",
    "flags_enabled",
    "activity_feed_enabled",
    "nsfw_detection_enabled",
    "art_of_the_day_enabled",
]


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


@router.get("/api/settings")
async def get_public_settings(
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Get public feature flags. No auth required.

    Returns a dict of feature_key -> enabled (bool).
    """
    result = await db.execute(
        select(SiteSetting).where(SiteSetting.key.in_(FEATURE_TOGGLES))
    )
    settings = result.scalars().all()

    flags: dict[str, bool] = {}
    for s in settings:
        flags[s.key] = s.value.lower() == "true"

    # Fill defaults for any missing keys
    for key in FEATURE_TOGGLES:
        if key not in flags:
            flags[key] = True

    return flags


@router.get("/api/admin/settings")
async def get_admin_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all site settings with metadata. Admin only."""
    _require_admin(current_user)

    result = await db.execute(select(SiteSetting))
    settings = result.scalars().all()

    existing_keys = {s.key for s in settings}
    items = []
    for s in settings:
        items.append({
            "key": s.key,
            "value": s.value,
            "updated_by": str(s.updated_by) if s.updated_by else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })

    # Include defaults for any missing toggles
    for key in FEATURE_TOGGLES:
        if key not in existing_keys:
            items.append({
                "key": key,
                "value": "true",
                "updated_by": None,
                "updated_at": None,
            })

    return items


@router.put("/api/admin/settings")
async def update_settings(
    updates: dict[str, str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update site settings. Admin only.

    Accepts a dict of key -> value pairs to update.
    Only known feature toggle keys are accepted.
    """
    _require_admin(current_user)

    now = datetime.now(timezone.utc)
    updated = {}

    for key, value in updates.items():
        if key not in FEATURE_TOGGLES:
            continue

        # Normalize boolean values
        normalized = "true" if value.lower() in ("true", "1", "yes", "on") else "false"

        result = await db.execute(select(SiteSetting).where(SiteSetting.key == key))
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = normalized
            setting.updated_by = current_user.id
            setting.updated_at = now
        else:
            setting = SiteSetting(
                key=key,
                value=normalized,
                updated_by=current_user.id,
                updated_at=now,
            )
            db.add(setting)

        updated[key] = normalized

    await db.commit()
    return updated
