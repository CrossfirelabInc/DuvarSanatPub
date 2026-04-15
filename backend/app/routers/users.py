"""User profile endpoints: public profile view, self-edit, avatar upload, and discoveries."""

import logging
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth import get_current_user
from app.clip_service import clip_service
from app.config import settings
from app.database import get_db
from app.models import Artwork, Photo, User, UserFollow
from app.rate_limit import limiter
from app.schemas import (
    UpdateProfileRequest,
    UserDiscoveryItem,
    UserPhotoItem,
    UserProfileResponse,
    UserResponse,
)

optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
) -> uuid.UUID | None:
    """Extract user_id from JWT if present, return None otherwise."""
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None

router = APIRouter(prefix="/api/users", tags=["users"])


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the authenticated user's profile fields.

    Validates display_name uniqueness if changed. Validates website URL format.
    Strips '@' prefix from social_links values.
    """
    if body.display_name is not None and body.display_name != current_user.display_name:
        # Check uniqueness
        result = await db.execute(
            select(User).where(
                User.display_name == body.display_name,
                User.id != current_user.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Display name already taken",
            )
        current_user.display_name = body.display_name

    if "bio" in body.model_fields_set:
        current_user.bio = body.bio or None

    if "tagline" in body.model_fields_set:
        current_user.tagline = body.tagline or None

    if "website" in body.model_fields_set:
        if body.website is not None and not body.website.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Website must start with http:// or https://",
            )
        current_user.website = body.website or None

    if "profile_type" in body.model_fields_set:
        allowed_profile_types = {"photographer", "artist", "explorer"}
        if body.profile_type is not None and body.profile_type not in allowed_profile_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"profile_type must be one of: {', '.join(sorted(allowed_profile_types))}",
            )
        if body.profile_type is not None:
            current_user.profile_type = body.profile_type

    if "social_links" in body.model_fields_set:
        if body.social_links is not None:
            # Strip leading '@' from all string values
            cleaned = {}
            for key, value in body.social_links.items():
                if isinstance(value, str):
                    cleaned[key] = value.lstrip("@")
                else:
                    cleaned[key] = value
            current_user.social_links = cleaned
        else:
            current_user.social_links = None

    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5 MB

logger = logging.getLogger(__name__)


def _detect_avatar_content_type(content: bytes) -> str | None:
    """Detect image content type from magic bytes."""
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("/me/avatar", response_model=UserResponse)
@limiter.limit("10/minute")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Upload a new profile picture for the authenticated user.

    Accepts JPEG, PNG, or WebP (max 5MB). Runs NSFW check.
    Saves to uploads/avatars/ and updates user.avatar_url.
    """
    content = await file.read()
    if len(content) > AVATAR_MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5MB limit.",
        )

    real_type = _detect_avatar_content_type(content)
    if real_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Upload JPEG, PNG, or WebP.",
        )

    # NSFW check
    if clip_service.is_loaded:
        try:
            is_safe, safety_score = clip_service.check_nsfw(content)
            if not is_safe:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This image has been flagged as inappropriate content and cannot be uploaded.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("NSFW check failed for avatar upload", exc_info=True)

    ext = "jpg" if real_type == "image/jpeg" else ("png" if real_type == "image/png" else "webp")
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"

    avatar_dir = Path(settings.UPLOAD_DIR) / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)

    file_path = avatar_dir / filename
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    current_user.avatar_url = f"/uploads/avatars/{filename}"
    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID | None = Depends(get_optional_user_id),
) -> UserProfileResponse:
    """Get a public user profile.

    Returns user info, aggregate counts (total photos, total artworks created,
    artworks discovered, unique artworks contributed), and paginated photos.
    """
    # Fetch the user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Count total photos uploaded by user
    photo_count_result = await db.execute(
        select(func.count()).select_from(Photo).where(Photo.user_id == user_id)
    )
    total_photos: int = photo_count_result.scalar_one()

    # Count total artworks created by user
    artwork_count_result = await db.execute(
        select(func.count()).select_from(Artwork).where(Artwork.created_by == user_id)
    )
    total_artworks: int = artwork_count_result.scalar_one()

    # Count artworks discovered (created_by = user_id) — same as total_artworks
    artworks_discovered: int = total_artworks

    # Count unique artworks contributed to (distinct artwork_id from user's photos)
    unique_contrib_result = await db.execute(
        select(func.count(func.distinct(Photo.artwork_id)))
        .select_from(Photo)
        .where(Photo.user_id == user_id, Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
    )
    unique_artworks_contributed: int = unique_contrib_result.scalar_one()

    # Fetch paginated photos by this user
    offset = (page - 1) * per_page
    photos_result = await db.execute(
        select(Photo)
        .where(Photo.user_id == user_id, Photo.is_deleted == False)  # noqa: E712
        .order_by(desc(Photo.date_uploaded))
        .offset(offset)
        .limit(per_page)
    )
    photos = photos_result.scalars().all()

    photo_items = [
        UserPhotoItem(
            id=p.id,
            image_url=p.image_url,
            thumbnail_url=p.thumbnail_url,
            artwork_id=p.artwork_id,
            date_uploaded=p.date_uploaded,
        )
        for p in photos
    ]

    # Check if current user is following this user
    is_following = False
    if current_user_id is not None and current_user_id != user_id:
        follow_result = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user_id,
                UserFollow.followed_user_id == user_id,
            )
        )
        is_following = follow_result.scalar_one_or_none() is not None

    return UserProfileResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        tagline=user.tagline,
        website=user.website,
        social_links=user.social_links,
        created_at=user.created_at,
        total_photos=total_photos,
        total_artworks=total_artworks,
        artworks_discovered=artworks_discovered,
        unique_artworks_contributed=unique_artworks_contributed,
        photos=photo_items,
        follower_count=user.follower_count,
        is_following=is_following,
    )


@router.get("/{user_id}/discoveries", response_model=list[UserDiscoveryItem])
async def get_user_discoveries(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[UserDiscoveryItem]:
    """Get artworks discovered (first cataloged) by a user.

    Public endpoint. Returns artworks where created_by = user_id,
    with the most recent photo as thumbnail, ordered by created_at desc.
    """
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Subquery: most recent photo per artwork (for thumbnails)
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url,
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.date_uploaded))
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    latest_photo = (
        select(latest_photo_subq.c.artwork_id, latest_photo_subq.c.image_url)
        .where(latest_photo_subq.c.rn == 1)
        .subquery()
    )

    query = (
        select(
            Artwork.id,
            Artwork.title,
            Artwork.status,
            Artwork.photo_count,
            Artwork.created_at,
            latest_photo.c.image_url.label("thumbnail_url"),
        )
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(Artwork.created_by == user_id)
        .order_by(desc(Artwork.created_at))
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        UserDiscoveryItem(
            id=row.id,
            title=row.title,
            status=row.status,
            thumbnail_url=row.thumbnail_url,
            photo_count=row.photo_count,
            created_at=row.created_at,
        )
        for row in rows
    ]
