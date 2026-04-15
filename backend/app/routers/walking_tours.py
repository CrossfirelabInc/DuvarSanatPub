"""Walking tour listing, detail, and generation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Artwork, Neighborhood, Photo, User, WalkingTour, WalkingTourStop
from app.schemas import TourDetailResponse, TourListItem, TourStopItem

router = APIRouter(prefix="/api/tours", tags=["tours"])


@router.get("", response_model=list[TourListItem])
async def list_tours(
    db: AsyncSession = Depends(get_db),
) -> list[TourListItem]:
    """List all walking tours.

    Public endpoint returning summary info for each tour.
    """
    result = await db.execute(
        select(WalkingTour, Neighborhood.name.label("neighborhood_name"))
        .outerjoin(Neighborhood, WalkingTour.neighborhood_id == Neighborhood.id)
        .order_by(WalkingTour.created_at)
    )
    rows = result.all()

    return [
        TourListItem(
            id=tour.id,
            title=tour.title,
            neighborhood_name=neighborhood_name,
            artwork_count=tour.artwork_count,
            total_distance_m=tour.total_distance_m,
            estimated_minutes=tour.estimated_minutes,
        )
        for tour, neighborhood_name in rows
    ]


@router.get("/{tour_id}", response_model=TourDetailResponse)
async def get_tour_detail(
    tour_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TourDetailResponse:
    """Get full tour detail with ordered stops.

    Public endpoint. Each stop includes artwork info and coordinates.
    """
    result = await db.execute(
        select(WalkingTour)
        .options(selectinload(WalkingTour.stops).selectinload(WalkingTourStop.artwork))
        .where(WalkingTour.id == tour_id)
    )
    tour = result.scalar_one_or_none()
    if tour is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")

    # Build stop items with coordinates
    stop_items: list[TourStopItem] = []
    for stop in sorted(tour.stops, key=lambda s: s.stop_order):
        artwork = stop.artwork

        # Extract coordinates from artwork location
        coord_result = await db.execute(
            select(
                ST_Y(cast(artwork.location, Geometry)).label("lat"),
                ST_X(cast(artwork.location, Geometry)).label("lng"),
            )
        )
        coords = coord_result.one()

        # Get thumbnail (most recent photo)
        photo_result = await db.execute(
            select(func.coalesce(Photo.thumbnail_url, Photo.image_url))
            .where(Photo.artwork_id == artwork.id, Photo.is_deleted == False)  # noqa: E712
            .order_by(Photo.created_at.desc())
            .limit(1)
        )
        thumbnail_row = photo_result.first()
        thumbnail_url = thumbnail_row[0] if thumbnail_row else None

        stop_items.append(
            TourStopItem(
                stop_order=stop.stop_order,
                artwork_id=artwork.id,
                artwork_title=artwork.title,
                thumbnail_url=thumbnail_url,
                latitude=coords.lat,
                longitude=coords.lng,
                distance_from_previous_m=stop.distance_from_previous_m,
            )
        )

    return TourDetailResponse(
        id=tour.id,
        title=tour.title,
        description=tour.description,
        stops=stop_items,
    )


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_tours(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate walking tours by clustering all active artworks (admin only).

    Algorithm:
    1. Delete all existing auto-generated tours (fresh regeneration).
    2. Fetch all active artworks with at least 1 photo.
    3. Sort by latitude then longitude and group into clusters of 3-6.
    4. Order stops within each cluster by nearest-neighbor (greedy).
    5. Compute approximate distances; only create tour if total < 5km.
    6. Estimate time at 80m/min walking + 3min per stop for viewing.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    # Delete old auto-generated tour stops first (FK constraint), then tours
    await db.execute(
        delete(WalkingTourStop).where(
            WalkingTourStop.tour_id.in_(
                select(WalkingTour.id).where(WalkingTour.is_auto_generated.is_(True))
            )
        )
    )
    await db.execute(
        delete(WalkingTour).where(WalkingTour.is_auto_generated.is_(True))
    )

    # Get all active artworks with photos
    result = await db.execute(
        select(
            Artwork.id,
            Artwork.title,
            ST_Y(cast(Artwork.location, Geometry)).label("lat"),
            ST_X(cast(Artwork.location, Geometry)).label("lng"),
        )
        .where(Artwork.status == "active", Artwork.photo_count >= 1)
    )
    artworks = result.all()

    if len(artworks) < 2:
        await db.commit()
        return {"tours_created": 0}

    # Clustering: sort by latitude then longitude, group into tours of 3-6
    # If remainder is 1-2, merge into last cluster
    sorted_aws = sorted(artworks, key=lambda a: (a.lat, a.lng))

    tours_created = 0
    i = 0
    while i < len(sorted_aws):
        remaining_count = len(sorted_aws) - i
        # If 7 or fewer left, take them all as one tour
        if remaining_count <= 7:
            cluster_size = remaining_count
        else:
            cluster_size = min(5, remaining_count)
        if cluster_size < 2:
            break
        cluster = sorted_aws[i : i + cluster_size]

        # Order by nearest-neighbor within cluster
        ordered = [cluster[0]]
        remaining = list(cluster[1:])
        while remaining:
            last = ordered[-1]
            nearest = min(
                remaining,
                key=lambda a: ((a.lat - last.lat) ** 2 + (a.lng - last.lng) ** 2),
            )
            ordered.append(nearest)
            remaining.remove(nearest)

        # Compute approximate distances in meters (at Istanbul latitude ~41 deg)
        total_dist = 0
        distances: list[int] = [0]
        for j in range(1, len(ordered)):
            dlat = (ordered[j].lat - ordered[j - 1].lat) * 111320
            dlng = (ordered[j].lng - ordered[j - 1].lng) * 111320 * 0.75  # cos(41) ~ 0.75
            dist = int((dlat**2 + dlng**2) ** 0.5)
            distances.append(dist)
            total_dist += dist

        # Only create tour if walkable (< 5km)
        if total_dist < 10000:  # 10km max (a long but doable art walk)
            tour = WalkingTour(
                title=f"Street Art Walk #{tours_created + 1}",
                description=f"A {len(ordered)}-stop walk covering {total_dist}m of street art",
                total_distance_m=total_dist,
                estimated_minutes=int(total_dist / 80) + len(ordered) * 3,
                artwork_count=len(ordered),
                is_auto_generated=True,
            )
            db.add(tour)
            await db.flush()

            for j, aw in enumerate(ordered):
                stop = WalkingTourStop(
                    tour_id=tour.id,
                    artwork_id=aw.id,
                    stop_order=j + 1,
                    distance_from_previous_m=distances[j],
                )
                db.add(stop)

            tours_created += 1

        i += cluster_size

    await db.commit()

    return {"tours_created": tours_created}
