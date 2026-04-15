"""Activity feed endpoint — recent platform activity."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select, union_all, literal
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.database import get_db
from app.models import Artwork, Comment, Photo, User

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
async def get_activity(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return recent platform activity: uploads, comments, and new artworks.

    Public endpoint. Returns a unified activity list sorted by time descending.
    """
    # Recent photo uploads
    photos_q = (
        select(
            Photo.id.label("item_id"),
            literal("photo_upload").label("activity_type"),
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("image_url"),
            User.display_name.label("user_name"),
            User.id.label("user_id"),
            Photo.artwork_id.label("target_id"),
            literal(None).label("content"),
            Photo.created_at.label("created_at"),
        )
        .join(User, User.id == Photo.user_id)
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .order_by(desc(Photo.created_at))
        .limit(limit)
    )

    # Recent comments
    comments_q = (
        select(
            Comment.id.label("item_id"),
            literal("comment").label("activity_type"),
            literal(None).label("image_url"),
            User.display_name.label("user_name"),
            User.id.label("user_id"),
            Comment.target_id.label("target_id"),
            Comment.content.label("content"),
            Comment.created_at.label("created_at"),
        )
        .join(User, User.id == Comment.user_id)
        .where(Comment.is_deleted == False)  # noqa: E712
        .order_by(desc(Comment.created_at))
        .limit(limit)
    )

    # Recent artworks created
    artworks_q = (
        select(
            Artwork.id.label("item_id"),
            literal("artwork_created").label("activity_type"),
            literal(None).label("image_url"),
            User.display_name.label("user_name"),
            User.id.label("user_id"),
            Artwork.id.label("target_id"),
            Artwork.title.label("content"),
            Artwork.created_at.label("created_at"),
        )
        .join(User, User.id == Artwork.created_by)
        .order_by(desc(Artwork.created_at))
        .limit(limit)
    )

    # Union all and sort
    combined = union_all(photos_q, comments_q, artworks_q).subquery()
    final = select(combined).order_by(desc(combined.c.created_at)).limit(limit)

    result = await db.execute(final)
    rows = result.all()

    return [
        {
            "id": str(row.item_id),
            "type": row.activity_type,
            "image_url": row.image_url,
            "user_name": row.user_name,
            "user_id": str(row.user_id),
            "target_id": str(row.target_id) if row.target_id else None,
            "content": row.content,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
