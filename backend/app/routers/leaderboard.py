"""Leaderboard endpoint: top photographers and artists."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Artist, ArtistSuggestion, Artwork, Photo, User
from app.schemas import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard(
    type: str = Query(..., pattern="^(photographers|artists)$"),
    period: str = Query("all_time", pattern="^(all_time|monthly)$"),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    """Get the leaderboard.

    - type=photographers: top 20 users by photo count
    - type=artists: top 20 artists by artwork_count
    - period=all_time|monthly (monthly only applies to photographers)

    Computed on-the-fly from live data.
    """
    entries: list[LeaderboardEntry] = []

    if type == "photographers":
        # Build photo count query
        photo_query = select(
            Photo.user_id,
            func.count().label("score"),
        ).group_by(Photo.user_id)

        if period == "monthly":
            # Photos uploaded this month
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            photo_query = photo_query.where(Photo.created_at >= month_start)

        photo_subq = photo_query.subquery()

        query = (
            select(
                User.id,
                User.display_name,
                User.avatar_url,
                User.follower_count,
                photo_subq.c.score,
            )
            .join(photo_subq, User.id == photo_subq.c.user_id)
            .order_by(desc(photo_subq.c.score))
            .limit(20)
        )

        result = await db.execute(query)
        rows = result.all()

        entries = [
            LeaderboardEntry(
                rank=idx + 1,
                id=row.id,
                name=row.display_name,
                score=row.score,
                follower_count=row.follower_count,
                metric="photos",
                avatar_url=row.avatar_url,
            )
            for idx, row in enumerate(rows)
        ]

    elif type == "artists":
        # Compute real artwork count (confirmed + pending suggestions)
        confirmed = (
            select(func.count())
            .select_from(Artwork)
            .where(Artwork.artist_id == Artist.id, Artwork.is_deleted == False)  # noqa: E712
            .correlate(Artist)
            .scalar_subquery()
        )
        pending = (
            select(func.count(func.distinct(ArtistSuggestion.artwork_id)))
            .where(
                ArtistSuggestion.artist_id == Artist.id,
                ArtistSuggestion.status == "pending",
            )
            .correlate(Artist)
            .scalar_subquery()
        )
        real_count = confirmed + pending

        query = (
            select(
                Artist.id,
                Artist.name,
                real_count.label("real_artwork_count"),
                Artist.follower_count,
            )
            .where(real_count > 0)
            .order_by(desc(real_count))
            .limit(20)
        )

        result = await db.execute(query)
        rows = result.all()

        entries = [
            LeaderboardEntry(
                rank=idx + 1,
                id=row.id,
                name=row.name,
                score=row.real_artwork_count,
                follower_count=row.follower_count,
                metric="artworks",
            )
            for idx, row in enumerate(rows)
        ]

    return LeaderboardResponse(type=type, period=period, entries=entries)
