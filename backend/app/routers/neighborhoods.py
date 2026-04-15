"""Neighborhood endpoints — list, detail with artworks, and auto-assign."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Artwork, Neighborhood, Photo, User
from app.schemas import ArtworkNearbyResponse, NeighborhoodDetailResponse, NeighborhoodResponse

router = APIRouter(prefix="/api/neighborhoods", tags=["neighborhoods"])


@router.get("", response_model=list[NeighborhoodResponse])
async def list_neighborhoods(
    db: AsyncSession = Depends(get_db),
) -> list[NeighborhoodResponse]:
    """List all neighborhoods with artwork_count > 0, ordered by artwork_count DESC."""
    stmt = (
        select(Neighborhood)
        .where(Neighborhood.artwork_count > 0)
        .order_by(desc(Neighborhood.artwork_count))
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


@router.get("/{slug}", response_model=NeighborhoodDetailResponse)
async def get_neighborhood_detail(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> NeighborhoodDetailResponse:
    """Get neighborhood detail with its artworks."""
    result = await db.execute(
        select(Neighborhood).where(Neighborhood.slug == slug)
    )
    neighborhood = result.scalar_one_or_none()
    if neighborhood is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Neighborhood not found",
        )

    # Subquery for latest photo per artwork (thumbnail)
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url,
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.created_at))
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

    artworks_stmt = (
        select(
            Artwork.id,
            Artwork.title,
            Artwork.status,
            ST_Y(cast(Artwork.location, Geometry)).label("latitude"),
            ST_X(cast(Artwork.location, Geometry)).label("longitude"),
            Artwork.photo_count,
            latest_photo.c.image_url.label("thumbnail_url"),
        )
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(Artwork.neighborhood_id == neighborhood.id)
        .order_by(desc(Artwork.created_at))
    )

    artworks_result = await db.execute(artworks_stmt)
    artwork_rows = artworks_result.all()

    artworks = [
        ArtworkNearbyResponse(
            id=row.id,
            title=row.title,
            status=row.status,
            latitude=row.latitude,
            longitude=row.longitude,
            photo_count=row.photo_count,
            thumbnail_url=row.thumbnail_url,
        )
        for row in artwork_rows
    ]

    return NeighborhoodDetailResponse(
        id=neighborhood.id,
        name=neighborhood.name,
        name_tr=neighborhood.name_tr,
        slug=neighborhood.slug,
        description=neighborhood.description,
        artwork_count=neighborhood.artwork_count,
        artworks=artworks,
    )


# Istanbul neighborhood approximate centers (lat, lng)
NEIGHBORHOOD_COORDS: dict[str, tuple[float, float]] = {
    "kadikoy": (40.9903, 29.0295),
    "beyoglu": (41.0336, 28.9770),
    "besiktas": (41.0430, 29.0070),
    "karakoy": (41.0220, 28.9740),
    "balat": (41.0292, 28.9485),
    "moda": (40.9830, 29.0245),
    "uskudar": (41.0250, 29.0150),
    "sisli": (41.0600, 28.9870),
    "taksim": (41.0370, 28.9850),
    "cihangir": (41.0326, 28.9823),
    "galata": (41.0256, 28.9741),
    "ortakoy": (41.0480, 29.0270),
    "nisantasi": (41.0480, 28.9940),
    "sultanahmet": (41.0054, 28.9768),
    "bahariye": (40.9900, 29.0230),
}

# Maximum distance in degrees (~3km) for neighborhood assignment
MAX_ASSIGN_DISTANCE = 0.03


def find_nearest_neighborhood_slug(lat: float, lng: float) -> str | None:
    """Find the nearest neighborhood slug for given coordinates.

    Returns the slug if within MAX_ASSIGN_DISTANCE (~3km), else None.
    """
    best_slug: str | None = None
    best_dist = float("inf")

    for slug, (nlat, nlng) in NEIGHBORHOOD_COORDS.items():
        dist = ((lat - nlat) ** 2 + (lng - nlng) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_slug = slug

    if best_slug is not None and best_dist < MAX_ASSIGN_DISTANCE:
        return best_slug
    return None


@router.post("/auto-assign")
async def auto_assign_neighborhoods(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Auto-assign artworks to their nearest neighborhood. Admin/moderator only.

    For each artwork without a neighborhood_id, finds the nearest neighborhood
    center point and assigns it if within ~3km. Also updates neighborhood
    artwork_count values.
    """
    if current_user.role not in ("admin", "moderator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    # Get neighborhoods with their slugs
    neighborhoods_result = await db.execute(select(Neighborhood))
    nh_list = neighborhoods_result.scalars().all()
    nh_by_slug = {n.slug: n for n in nh_list}

    # Get artworks without neighborhood, with extracted coordinates
    artworks_result = await db.execute(
        select(
            Artwork.id,
            ST_Y(cast(Artwork.location, Geometry)).label("lat"),
            ST_X(cast(Artwork.location, Geometry)).label("lng"),
        ).where(Artwork.neighborhood_id.is_(None))
    )

    assigned = 0
    for aw in artworks_result.all():
        best_slug = find_nearest_neighborhood_slug(aw.lat, aw.lng)

        if best_slug and best_slug in nh_by_slug:
            await db.execute(
                update(Artwork)
                .where(Artwork.id == aw.id)
                .values(neighborhood_id=nh_by_slug[best_slug].id)
            )
            assigned += 1

    # Update neighborhood artwork counts
    for nh in nh_list:
        count = await db.scalar(
            select(func.count()).select_from(Artwork).where(Artwork.neighborhood_id == nh.id)
        )
        await db.execute(
            update(Neighborhood).where(Neighborhood.id == nh.id).values(artwork_count=count or 0)
        )

    await db.commit()
    return {"assigned": assigned}
