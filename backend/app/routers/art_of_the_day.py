"""Art of the Day endpoints — daily featured artwork."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.art_of_the_day_service import pick_artwork_id
from app.config import settings
from app.database import get_db
from app.models import ArtOfTheDay, Artist, Artwork, Photo
from app.schemas import ArtOfTheDayHistoryItem, ArtOfTheDayResponse

router = APIRouter(prefix="/api/art-of-the-day", tags=["art-of-the-day"])


@router.get("", response_model=ArtOfTheDayResponse | None)
async def get_art_of_the_day(
    db: AsyncSession = Depends(get_db),
) -> ArtOfTheDayResponse | None:
    """Return today's featured artwork, lazily generating a pick if needed.

    Returns null JSON response if no eligible artworks exist.
    """
    today = date.today()

    # 1. Check if a row already exists for today
    existing_result = await db.execute(
        select(ArtOfTheDay).where(ArtOfTheDay.featured_date == today)
    )
    aotd = existing_result.scalar_one_or_none()

    if aotd is None:
        # 2. Query all artworks with at least one photo
        eligible_result = await db.execute(
            select(Artwork.id).where(Artwork.photo_count >= 1, Artwork.is_deleted == False)  # noqa: E712
        )
        eligible_ids = [str(row[0]) for row in eligible_result.all()]

        if not eligible_ids:
            return None

        # 3. Get recently featured artwork IDs (last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        recent_result = await db.execute(
            select(ArtOfTheDay.artwork_id).where(
                ArtOfTheDay.featured_date >= thirty_days_ago
            )
        )
        recently_featured_ids = {str(row[0]) for row in recent_result.all()}

        # 4. Pick deterministically
        picked_id = pick_artwork_id(
            eligible_ids, recently_featured_ids, today, settings.JWT_SECRET
        )
        if picked_id is None:
            return None

        # 5. Create the row
        aotd = ArtOfTheDay(artwork_id=picked_id, featured_date=today)
        db.add(aotd)
        await db.commit()
        await db.refresh(aotd)

    # 6. Build the response with full artwork details
    # Latest photo subquery
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


@router.get("/history", response_model=list[ArtOfTheDayHistoryItem])
async def get_art_of_the_day_history(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ArtOfTheDayHistoryItem]:
    """Return recently featured artworks ordered by date descending."""

    # Latest photo subquery for thumbnails (use image_url since thumbnail_url is not generated)
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url.label("thumbnail_url"),
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.created_at))
            .label("rn"),
        )
        .subquery()
    )

    stmt = (
        select(
            ArtOfTheDay.artwork_id,
            ArtOfTheDay.featured_date,
            Artwork.title,
            Artist.name.label("artist_name"),
            latest_photo_subq.c.thumbnail_url,
        )
        .join(Artwork, ArtOfTheDay.artwork_id == Artwork.id)
        .outerjoin(Artist, Artwork.artist_id == Artist.id)
        .outerjoin(
            latest_photo_subq,
            (latest_photo_subq.c.artwork_id == Artwork.id)
            & (latest_photo_subq.c.rn == 1),
        )
        .order_by(desc(ArtOfTheDay.featured_date))
        .limit(limit)
    )

    rows = (await db.execute(stmt)).all()
    return [
        ArtOfTheDayHistoryItem(
            artwork_id=row.artwork_id,
            title=row.title,
            artist_name=row.artist_name,
            thumbnail_url=row.thumbnail_url,
            featured_date=row.featured_date.isoformat()
            if hasattr(row.featured_date, "isoformat")
            else str(row.featured_date),
        )
        for row in rows
    ]
