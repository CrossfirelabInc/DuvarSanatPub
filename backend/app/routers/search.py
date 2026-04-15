"""Search endpoints for artworks and artists."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Artist, Artwork, Photo
from app.schemas import SearchArtistItem, SearchArtworkItem, SearchResponse

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    type: str = Query("all", pattern="^(all|artworks|artists)$"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search artworks and artists using ILIKE text matching.

    Public endpoint. Searches artwork title/description and artist name/aliases.
    Returns up to 20 results per type.

    Query params:
        q: search query string
        type: 'all', 'artworks', or 'artists'
    """
    pattern = f"%{q}%"
    artworks: list[SearchArtworkItem] = []
    artists: list[SearchArtistItem] = []

    if type in ("all", "artworks"):
        # Subquery for thumbnail
        latest_photo_subq = (
            select(
                Photo.artwork_id,
                Photo.image_url,
                func.row_number()
                .over(
                    partition_by=Photo.artwork_id,
                    order_by=desc(Photo.date_taken).nullslast(),
                )
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

        artwork_query = (
            select(
                Artwork.id,
                Artwork.title,
                Artwork.status,
                latest_photo.c.image_url.label("thumbnail_url"),
                Artist.name.label("artist_name"),
            )
            .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
            .outerjoin(Artist, Artwork.artist_id == Artist.id)
            .where(
                (Artwork.title.ilike(pattern)) | (Artwork.description.ilike(pattern))
            )
            .order_by(desc(Artwork.created_at))
            .limit(20)
        )

        result = await db.execute(artwork_query)
        rows = result.all()
        artworks = [
            SearchArtworkItem(
                id=row.id,
                title=row.title,
                thumbnail_url=row.thumbnail_url,
                status=row.status,
                artist_name=row.artist_name,
            )
            for row in rows
        ]

    if type in ("all", "artists"):
        # Search artists by name or aliases (using ANY for array search)
        artist_query = (
            select(Artist.id, Artist.name, Artist.artwork_count)
            .where(
                (Artist.name.ilike(pattern))
                | (func.array_to_string(Artist.aliases, ",").ilike(pattern))
            )
            .order_by(desc(Artist.artwork_count))
            .limit(20)
        )

        result = await db.execute(artist_query)
        rows = result.all()
        artists = [
            SearchArtistItem(
                id=row.id,
                name=row.name,
                artwork_count=row.artwork_count,
            )
            for row in rows
        ]

    return SearchResponse(artworks=artworks, artists=artists)
