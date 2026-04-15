"""Homepage endpoint — returns all homepage data in a single call."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.art_of_the_day_service import pick_artwork_id
from app.config import settings
from app.database import get_db
from app.models import ArtOfTheDay, Artist, Artwork, Neighborhood, Photo, User
from app.rate_limit import limiter
from app.schemas import (
    ArtOfTheDayResponse,
    HomepageResponse,
    HomepageStatsResponse,
    NeighborhoodResponse,
    RecentDiscoveryItem,
    TopArtworkItem,
    TopContributorItem,
    WallChangedItem,
)

router = APIRouter(tags=["homepage"])

CONSENSUS_THRESHOLD = 3


@router.get("/api/homepage", response_model=HomepageResponse)
@limiter.limit("30/minute")
async def get_homepage(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HomepageResponse:
    """Return all homepage data in one call to avoid multiple round-trips.

    Includes: art of the day, platform stats, walls changed (before/after),
    recent discoveries, active neighborhoods, and mysteries count.
    """
    art_of_the_day = await _get_art_of_the_day(db)

    stats = await _get_stats(db)

    walls_changed = await _get_walls_changed(db)

    recent_discoveries = await _get_recent_discoveries(db)

    neighborhoods = await _get_active_neighborhoods(db)

    mysteries_count = await db.scalar(
        select(func.count()).select_from(Artwork).where(
            Artwork.artist_id.is_(None), Artwork.is_deleted == False  # noqa: E712
        )
    ) or 0

    top_contributors = await _get_top_contributors(db)

    top_artworks = await _get_top_artworks(db)

    return HomepageResponse(
        art_of_the_day=art_of_the_day,
        stats=stats,
        walls_changed=walls_changed,
        recent_discoveries=recent_discoveries,
        neighborhoods=neighborhoods,
        mysteries_count=mysteries_count,
        top_contributors=top_contributors,
        top_artworks=top_artworks,
    )


async def _get_art_of_the_day(db: AsyncSession) -> ArtOfTheDayResponse | None:
    """Get or create today's Art of the Day entry."""
    today = date.today()

    existing_result = await db.execute(
        select(ArtOfTheDay).where(ArtOfTheDay.featured_date == today)
    )
    aotd = existing_result.scalar_one_or_none()

    if aotd is None:
        eligible_result = await db.execute(
            select(Artwork.id).where(Artwork.photo_count >= 1)
        )
        eligible_ids = [str(row[0]) for row in eligible_result.all()]

        if not eligible_ids:
            return None

        thirty_days_ago = today - timedelta(days=30)
        recent_result = await db.execute(
            select(ArtOfTheDay.artwork_id).where(
                ArtOfTheDay.featured_date >= thirty_days_ago
            )
        )
        recently_featured_ids = {str(row[0]) for row in recent_result.all()}

        picked_id = pick_artwork_id(
            eligible_ids, recently_featured_ids, today, settings.JWT_SECRET
        )
        if picked_id is None:
            return None

        aotd = ArtOfTheDay(artwork_id=picked_id, featured_date=today)
        db.add(aotd)
        await db.commit()
        await db.refresh(aotd)

    # Build response with full artwork details
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url,
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.created_at))
            .label("rn"),
        )
        .where(Photo.artwork_id == aotd.artwork_id)
        .subquery()
    )

    stmt = (
        select(
            Artwork.id,
            Artwork.title,
            Artwork.description,
            Artwork.photo_count,
            Artist.name.label("artist_name"),
            ST_X(cast(Artwork.location, Geometry)).label("longitude"),
            ST_Y(cast(Artwork.location, Geometry)).label("latitude"),
            latest_photo_subq.c.image_url.label("photo_url"),
        )
        .outerjoin(Artist, Artwork.artist_id == Artist.id)
        .outerjoin(
            latest_photo_subq,
            (latest_photo_subq.c.artwork_id == Artwork.id)
            & (latest_photo_subq.c.rn == 1),
        )
        .where(Artwork.id == aotd.artwork_id)
    )

    row = (await db.execute(stmt)).first()
    if row is None:
        return None

    return ArtOfTheDayResponse(
        artwork_id=row.id,
        title=row.title,
        description=row.description,
        artist_name=row.artist_name,
        latitude=row.latitude,
        longitude=row.longitude,
        featured_date=today.isoformat(),
        photo_url=row.photo_url,
        photo_count=row.photo_count,
    )


async def _get_stats(db: AsyncSession) -> HomepageStatsResponse:
    """Get platform-wide statistics (excludes soft-deleted content)."""
    total_artworks = await db.scalar(
        select(func.count()).select_from(Artwork).where(Artwork.is_deleted == False)  # noqa: E712
    ) or 0
    total_photos = await db.scalar(
        select(func.count()).select_from(Photo).where(Photo.is_deleted == False)  # noqa: E712
    ) or 0
    total_artists = await db.scalar(select(func.count()).select_from(Artist)) or 0

    seven_days_ago = date.today() - timedelta(days=7)
    walls_changed_this_week = await db.scalar(
        select(func.count(func.distinct(Photo.artwork_id)))
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .where(Photo.is_deleted == False)  # noqa: E712
        .where(Photo.created_at >= seven_days_ago)
    ) or 0

    return HomepageStatsResponse(
        total_artworks=total_artworks,
        total_photos=total_photos,
        total_artists=total_artists,
        walls_changed_this_week=walls_changed_this_week,
    )


async def _get_walls_changed(db: AsyncSession) -> list[WallChangedItem]:
    """Get artworks with new photos in the last 7 days, with before/after URLs."""
    seven_days_ago = date.today() - timedelta(days=7)

    # Find artworks that have photos uploaded in last 7 days
    recent_artwork_ids_subq = (
        select(func.distinct(Photo.artwork_id).label("artwork_id"))
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .where(Photo.created_at >= seven_days_ago)
        .subquery()
    )

    # Oldest photo per artwork (prefer thumbnail)
    oldest_photo_subq = (
        select(
            Photo.artwork_id,
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("url"),
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=Photo.created_at.asc())
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    oldest_photo = (
        select(
            oldest_photo_subq.c.artwork_id,
            oldest_photo_subq.c.url.label("oldest_url"),
        )
        .where(oldest_photo_subq.c.rn == 1)
        .subquery()
    )

    # Newest photo per artwork (prefer thumbnail)
    newest_photo_subq = (
        select(
            Photo.artwork_id,
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("url"),
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=Photo.created_at.desc())
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    newest_photo = (
        select(
            newest_photo_subq.c.artwork_id,
            newest_photo_subq.c.url.label("newest_url"),
        )
        .where(newest_photo_subq.c.rn == 1)
        .subquery()
    )

    # Total votes per artwork
    vote_sum_subq = (
        select(
            Photo.artwork_id,
            func.coalesce(func.sum(Photo.vote_count), 0).label("total_votes"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .group_by(Photo.artwork_id)
        .subquery()
    )

    stmt = (
        select(
            Artwork.id.label("artwork_id"),
            Artwork.title,
            Artist.name.label("artist_name"),
            Neighborhood.name.label("neighborhood"),
            oldest_photo.c.oldest_url.label("oldest_photo_url"),
            newest_photo.c.newest_url.label("newest_photo_url"),
            Artwork.photo_count,
        )
        .join(recent_artwork_ids_subq, Artwork.id == recent_artwork_ids_subq.c.artwork_id)
        .outerjoin(Artist, Artwork.artist_id == Artist.id)
        .outerjoin(Neighborhood, Artwork.neighborhood_id == Neighborhood.id)
        .outerjoin(oldest_photo, Artwork.id == oldest_photo.c.artwork_id)
        .outerjoin(newest_photo, Artwork.id == newest_photo.c.artwork_id)
        .outerjoin(vote_sum_subq, Artwork.id == vote_sum_subq.c.artwork_id)
        .where(Artwork.is_deleted == False)  # noqa: E712
        .order_by(desc(func.coalesce(vote_sum_subq.c.total_votes, 0)))
        .limit(10)
    )

    rows = (await db.execute(stmt)).all()
    return [
        WallChangedItem(
            artwork_id=row.artwork_id,
            title=row.title,
            artist_name=row.artist_name,
            neighborhood=row.neighborhood,
            oldest_photo_url=row.oldest_photo_url,
            newest_photo_url=row.newest_photo_url,
            photo_count=row.photo_count,
        )
        for row in rows
    ]


async def _get_recent_discoveries(db: AsyncSession) -> list[RecentDiscoveryItem]:
    """Get newest artworks, limit 8."""
    # Most recent photo per artwork for thumbnail (prefer thumbnail_url)
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("thumb"),
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.created_at))
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    latest_photo = (
        select(latest_photo_subq.c.artwork_id, latest_photo_subq.c.thumb)
        .where(latest_photo_subq.c.rn == 1)
        .subquery()
    )

    stmt = (
        select(
            Artwork.id,
            Artwork.title,
            Artist.name.label("artist_name"),
            latest_photo.c.thumb.label("thumbnail_url"),
            Neighborhood.name.label("neighborhood"),
            Artwork.created_at,
        )
        .outerjoin(Artist, Artwork.artist_id == Artist.id)
        .outerjoin(Neighborhood, Artwork.neighborhood_id == Neighborhood.id)
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(Artwork.is_deleted == False)  # noqa: E712
        .order_by(desc(Artwork.created_at))
        .limit(8)
    )

    rows = (await db.execute(stmt)).all()
    return [
        RecentDiscoveryItem(
            id=row.id,
            title=row.title,
            artist_name=row.artist_name,
            thumbnail_url=row.thumbnail_url,
            neighborhood=row.neighborhood,
            created_at=row.created_at,
        )
        for row in rows
    ]


async def _get_active_neighborhoods(db: AsyncSession) -> list[NeighborhoodResponse]:
    """Get neighborhoods with artwork_count > 0, ordered by count DESC, limit 6."""
    stmt = (
        select(Neighborhood)
        .where(Neighborhood.artwork_count > 0)
        .order_by(desc(Neighborhood.artwork_count))
        .limit(6)
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        NeighborhoodResponse(
            id=n.id,
            name=n.name,
            slug=n.slug,
            artwork_count=n.artwork_count,
        )
        for n in rows
    ]


async def _get_top_contributors(db: AsyncSession) -> list[TopContributorItem]:
    """Get the top 5 users by photo count, with their artwork count."""
    artwork_count_subq = (
        select(
            Artwork.created_by.label("user_id"),
            func.count(Artwork.id).label("artwork_count"),
        )
        .group_by(Artwork.created_by)
        .subquery()
    )

    stmt = (
        select(
            User.id,
            User.display_name,
            User.avatar_url,
            func.count(Photo.id).label("photo_count"),
            func.coalesce(artwork_count_subq.c.artwork_count, 0).label("artwork_count"),
        )
        .join(Photo, Photo.user_id == User.id)
        .outerjoin(artwork_count_subq, artwork_count_subq.c.user_id == User.id)
        .group_by(User.id, User.display_name, User.avatar_url, artwork_count_subq.c.artwork_count)
        .order_by(desc(func.count(Photo.id)))
        .limit(5)
    )

    rows = (await db.execute(stmt)).all()
    return [
        TopContributorItem(
            user_id=row.id,
            display_name=row.display_name,
            avatar_url=row.avatar_url,
            photo_count=row.photo_count,
            artwork_count=row.artwork_count,
        )
        for row in rows
    ]


async def _get_top_artworks(db: AsyncSession) -> list[TopArtworkItem]:
    """Get top 5 artworks by total vote count across all their photos."""
    # Subquery: sum vote_count per artwork
    top_art_subq = (
        select(
            Photo.artwork_id,
            func.sum(Photo.vote_count).label("total_votes"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .group_by(Photo.artwork_id)
        .having(func.sum(Photo.vote_count) > 0)
        .subquery()
    )

    # Latest photo per artwork for thumbnail (prefer thumbnail_url)
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("thumb"),
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.created_at))
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    latest_photo = (
        select(latest_photo_subq.c.artwork_id, latest_photo_subq.c.thumb)
        .where(latest_photo_subq.c.rn == 1)
        .subquery()
    )

    top_artworks_query = (
        select(
            Artwork.id,
            Artwork.title,
            latest_photo.c.thumb.label("thumbnail_url"),
            top_art_subq.c.total_votes,
        )
        .join(top_art_subq, Artwork.id == top_art_subq.c.artwork_id)
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .order_by(desc(top_art_subq.c.total_votes))
        .limit(5)
    )

    rows = (await db.execute(top_artworks_query)).all()
    return [
        TopArtworkItem(
            id=row.id,
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            total_votes=int(row.total_votes),
        )
        for row in rows
    ]
