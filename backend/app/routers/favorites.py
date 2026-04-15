"""User favorites endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Artwork, Photo, User, UserFavorite
from app.schemas import FavoriteItem, FavoriteResponse

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


@router.post("/{artwork_id}", response_model=FavoriteResponse)
async def toggle_favorite(
    artwork_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteResponse:
    """Toggle a favorite on an artwork.

    If the user has already favorited the artwork, it is removed.
    If not, it is added. Returns the current favorited state.
    """
    # Verify artwork exists
    result = await db.execute(select(Artwork).where(Artwork.id == artwork_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artwork not found",
        )

    # Check existing favorite
    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.artwork_id == artwork_id,
        )
    )
    fav = existing.scalar_one_or_none()

    if fav is not None:
        await db.delete(fav)
        await db.commit()
        return FavoriteResponse(favorited=False)
    else:
        new_fav = UserFavorite(
            user_id=current_user.id,
            artwork_id=artwork_id,
        )
        db.add(new_fav)
        await db.commit()
        return FavoriteResponse(favorited=True)


@router.get("/{artwork_id}/status", response_model=FavoriteResponse)
async def favorite_status(
    artwork_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteResponse:
    """Check if the current user has favorited a specific artwork."""
    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.artwork_id == artwork_id,
        )
    )
    return FavoriteResponse(favorited=existing.scalar_one_or_none() is not None)


@router.get("", response_model=list[FavoriteItem])
async def list_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FavoriteItem]:
    """List the authenticated user's favorited artworks.

    Returns artworks with thumbnail, ordered by favorite creation date desc.
    """
    # Subquery: most recent photo per artwork (for thumbnails)
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url,
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.date_taken).nullslast())
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
            Artwork.id.label("artwork_id"),
            Artwork.title,
            Artwork.status,
            latest_photo.c.image_url.label("thumbnail_url"),
            UserFavorite.created_at,
        )
        .join(Artwork, Artwork.id == UserFavorite.artwork_id)
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(UserFavorite.user_id == current_user.id)
        .order_by(desc(UserFavorite.created_at))
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        FavoriteItem(
            artwork_id=row.artwork_id,
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            status=row.status,
            created_at=row.created_at,
        )
        for row in rows
    ]
