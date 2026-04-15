"""Artwork CRUD, photo linking, nearby search, and map data endpoints."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import Request
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from jose import JWTError, jwt
from sqlalchemy import cast, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Artist, ArtistSuggestion, Artwork, Neighborhood, Photo, User, UserFavorite
from app.notification_utils import create_notification
from app.rate_limit import limiter
from app.schemas import (
    ArtistSuggestionResponse,
    ArtworkDetailResponse,
    ArtworkMapItem,
    ArtworkNearbyResponse,
    ArtworkResponse,
    ArtworkStatsResponse,
    CreateArtworkRequest,
    LinkPhotoRequest,
    PhotoDetailResponse,
    SimilarArtworkItem,
    StyleSimilarArtworkItem,
    SuggestArtistRequest,
    SuggestionItem,
)

logger = logging.getLogger(__name__)

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

router = APIRouter(prefix="/api/artworks", tags=["artworks"])


def _make_artwork_response(artwork: Artwork, lat: float, lng: float) -> ArtworkResponse:
    """Build an ArtworkResponse from an Artwork model and extracted coordinates."""
    return ArtworkResponse(
        id=artwork.id,
        title=artwork.title,
        description=artwork.description,
        latitude=lat,
        longitude=lng,
        status=artwork.status,
        photo_count=artwork.photo_count,
        artist_id=artwork.artist_id,
        created_by=artwork.created_by,
        created_at=artwork.created_at,
        updated_at=artwork.updated_at,
    )


@router.post("", response_model=ArtworkResponse, status_code=status.HTTP_201_CREATED)
async def create_artwork(
    body: CreateArtworkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtworkResponse:
    """Create a new artwork and link a photo to it.

    Creates an artwork at the given coordinates, sets created_by to the
    authenticated user, and links the specified photo to the artwork.
    """
    # Verify the photo exists and belongs to the current user
    result = await db.execute(select(Photo).where(Photo.id == body.photo_id))
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only link your own photos")

    # Create artwork with PostGIS point
    wkt_point = f"SRID=4326;POINT({body.longitude} {body.latitude})"

    # Auto-assign neighborhood based on coordinates
    from app.routers.neighborhoods import find_nearest_neighborhood_slug

    neighborhood_id = None
    nearest_slug = find_nearest_neighborhood_slug(body.latitude, body.longitude)
    if nearest_slug:
        nh_result = await db.execute(
            select(Neighborhood.id).where(Neighborhood.slug == nearest_slug)
        )
        nh_row = nh_result.scalar_one_or_none()
        if nh_row is not None:
            neighborhood_id = nh_row

    artwork = Artwork(
        title=body.title,
        description=body.description,
        location=wkt_point,
        created_by=current_user.id,
        photo_count=0,
        neighborhood_id=neighborhood_id,
    )
    db.add(artwork)
    await db.flush()

    # Link the photo to this artwork
    photo.artwork_id = artwork.id

    # Atomic increment of photo_count at the SQL level
    await db.execute(
        update(Artwork)
        .where(Artwork.id == artwork.id)
        .values(photo_count=Artwork.photo_count + 1)
    )

    # Increment neighborhood artwork_count if assigned
    if neighborhood_id is not None:
        await db.execute(
            update(Neighborhood)
            .where(Neighborhood.id == neighborhood_id)
            .values(artwork_count=Neighborhood.artwork_count + 1)
        )

    await db.commit()
    await db.refresh(artwork)

    return _make_artwork_response(artwork, body.latitude, body.longitude)


@router.patch("/{artwork_id}/link-photo", response_model=ArtworkResponse)
async def link_photo(
    artwork_id: uuid.UUID,
    body: LinkPhotoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtworkResponse:
    """Link an existing photo to an existing artwork.

    Increments the artwork's photo_count and sets the photo's artwork_id.
    """
    # Get the artwork
    result = await db.execute(select(Artwork).where(Artwork.id == artwork_id))
    artwork = result.scalar_one_or_none()
    if artwork is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artwork not found")

    # Get the photo
    result = await db.execute(select(Photo).where(Photo.id == body.photo_id))
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only link your own photos")

    # If photo is already linked to this artwork, return as-is (no double-count)
    if photo.artwork_id == artwork.id:
        coord_query = select(
            ST_Y(cast(artwork.location, Geometry)).label("lat"),
            ST_X(cast(artwork.location, Geometry)).label("lng"),
        )
        coord_result = await db.execute(coord_query)
        coords = coord_result.one()
        return _make_artwork_response(artwork, coords.lat, coords.lng)

    # If photo was linked to a different artwork, atomically decrement that artwork's count
    old_artwork_id = photo.artwork_id
    if old_artwork_id is not None:
        await db.execute(
            update(Artwork)
            .where(Artwork.id == old_artwork_id)
            .values(photo_count=Artwork.photo_count - 1)
        )

    # Link photo to this artwork
    photo.artwork_id = artwork.id

    # Atomic increment of photo_count at the SQL level
    await db.execute(
        update(Artwork)
        .where(Artwork.id == artwork.id)
        .values(photo_count=Artwork.photo_count + 1)
    )

    # Notify the artwork creator if the linker is someone else
    if artwork.created_by != current_user.id:
        await create_notification(
            db,
            user_id=artwork.created_by,
            type="new_photo",
            title="New photo on your artwork",
            message=f"{current_user.display_name} added a photo to your artwork.",
            link=f"/artworks/{artwork.id}",
        )

    await db.commit()
    await db.refresh(artwork)

    # Extract coordinates from artwork location
    coord_query = select(
        ST_Y(cast(artwork.location, Geometry)).label("lat"),
        ST_X(cast(artwork.location, Geometry)).label("lng"),
    )
    coord_result = await db.execute(coord_query)
    coords = coord_result.one()

    return _make_artwork_response(artwork, coords.lat, coords.lng)


CONSENSUS_THRESHOLD = 3


@router.post("/{artwork_id}/suggest-artist", response_model=ArtistSuggestionResponse)
@limiter.limit("10/minute")
async def suggest_artist(
    request: Request,
    artwork_id: uuid.UUID,
    body: SuggestArtistRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtistSuggestionResponse:
    """Suggest an artist for an artwork using consensus model.

    Creates an ArtistSuggestion record. If 3+ users suggest the same
    artist, the artwork is automatically attributed to that artist.
    Returns 409 if the user already suggested an artist for this artwork.
    """
    # Fetch artwork
    result = await db.execute(select(Artwork).where(Artwork.id == artwork_id))
    artwork = result.scalar_one_or_none()
    if artwork is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artwork not found"
        )

    # Check if user already suggested for this artwork
    existing_suggestion = await db.execute(
        select(ArtistSuggestion).where(
            ArtistSuggestion.artwork_id == artwork_id,
            ArtistSuggestion.suggested_by == current_user.id,
        )
    )
    if existing_suggestion.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already suggested an artist for this artwork",
        )

    # Look up artist by name (case-insensitive)
    result = await db.execute(
        select(Artist).where(func.lower(Artist.name) == body.artist_name.strip().lower())
    )
    artist = result.scalar_one_or_none()

    if artist is None:
        # Create a new artist with artwork_count=0
        artist = Artist(name=body.artist_name.strip(), artwork_count=0)
        db.add(artist)
        await db.flush()

    # Create the suggestion record
    suggestion = ArtistSuggestion(
        artwork_id=artwork_id,
        artist_id=artist.id,
        suggested_name=body.artist_name.strip(),
        suggested_by=current_user.id,
        status="pending",
    )
    db.add(suggestion)
    await db.flush()

    # Count suggestions grouped by artist_id for this artwork
    consensus_result = await db.execute(
        select(
            ArtistSuggestion.artist_id,
            func.count().label("cnt"),
        )
        .where(ArtistSuggestion.artwork_id == artwork_id)
        .where(ArtistSuggestion.status == "pending")
        .group_by(ArtistSuggestion.artist_id)
        .order_by(desc(func.count()))
    )
    grouped = consensus_result.all()

    consensus_reached = False
    for row in grouped:
        if row.cnt >= CONSENSUS_THRESHOLD and row.artist_id is not None:
            # Auto-accept: set artwork.artist_id
            consensus_artist_id = row.artist_id

            # Decrement old artist count if needed
            old_artist_id = artwork.artist_id
            if old_artist_id is not None and old_artist_id != consensus_artist_id:
                await db.execute(
                    update(Artist)
                    .where(Artist.id == old_artist_id)
                    .values(artwork_count=Artist.artwork_count - 1)
                )

            # Set artwork artist and increment count
            if artwork.artist_id != consensus_artist_id:
                artwork.artist_id = consensus_artist_id
                await db.execute(
                    update(Artist)
                    .where(Artist.id == consensus_artist_id)
                    .values(artwork_count=Artist.artwork_count + 1)
                )

            # Update matching suggestions to accepted
            await db.execute(
                update(ArtistSuggestion)
                .where(ArtistSuggestion.artwork_id == artwork_id)
                .where(ArtistSuggestion.artist_id == consensus_artist_id)
                .values(status="accepted")
            )

            consensus_reached = True
            break

    await db.commit()
    await db.refresh(suggestion)

    # Build suggestions summary
    suggestions = await _get_suggestion_summary(db, artwork_id)

    return ArtistSuggestionResponse(
        artwork_id=artwork_id,
        suggestion_id=suggestion.id,
        artist_name=body.artist_name.strip(),
        status=suggestion.status,
        consensus_reached=consensus_reached,
        suggestions=suggestions,
    )


async def _get_suggestion_summary(
    db: AsyncSession, artwork_id: uuid.UUID
) -> list[SuggestionItem]:
    """Get a summary of suggestions for an artwork grouped by artist."""
    result = await db.execute(
        select(
            ArtistSuggestion.suggested_name,
            func.count().label("cnt"),
            ArtistSuggestion.status,
        )
        .where(ArtistSuggestion.artwork_id == artwork_id)
        .group_by(ArtistSuggestion.suggested_name, ArtistSuggestion.status)
        .order_by(desc(func.count()))
    )
    rows = result.all()
    return [
        SuggestionItem(
            artist_name=row.suggested_name,
            count=row.cnt,
            status=row.status,
        )
        for row in rows
    ]


@router.get("/stats", response_model=ArtworkStatsResponse)
async def get_artwork_stats(
    db: AsyncSession = Depends(get_db),
) -> ArtworkStatsResponse:
    """Return platform-wide counts. Public endpoint used by the map stats bar."""
    total_artworks = await db.scalar(
        select(func.count()).select_from(Artwork).where(Artwork.is_deleted == False)  # noqa: E712
    ) or 0
    artworks_without_artist = (
        await db.scalar(
            select(func.count()).select_from(Artwork).where(
                Artwork.artist_id.is_(None), Artwork.is_deleted == False  # noqa: E712
            )
        )
        or 0
    )
    total_photos = await db.scalar(
        select(func.count()).select_from(Photo).where(Photo.is_deleted == False)  # noqa: E712
    ) or 0
    total_artists = await db.scalar(select(func.count()).select_from(Artist)) or 0

    return ArtworkStatsResponse(
        total_artworks=total_artworks,
        artworks_without_artist=artworks_without_artist,
        total_photos=total_photos,
        total_artists=total_artists,
    )


@router.get("/nearby", response_model=list[ArtworkNearbyResponse])
async def get_nearby_artworks(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius: float = Query(50, gt=0, le=50000),
    db: AsyncSession = Depends(get_db),
) -> list[ArtworkNearbyResponse]:
    """Find artworks within a radius (meters) of a given point.

    Public endpoint. Returns up to 20 artworks ordered by distance,
    each including the most recent photo's image_url as a thumbnail.
    """
    # Build the reference point as geography
    ref_point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)

    # Subquery to get the most recent photo's image_url per artwork
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url,
            Photo.thumbnail_url,
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.date_taken).nullslast())
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    latest_photo = (
        select(latest_photo_subq.c.artwork_id, latest_photo_subq.c.image_url, latest_photo_subq.c.thumbnail_url)
        .where(latest_photo_subq.c.rn == 1)
        .subquery()
    )

    # Main query
    query = (
        select(
            Artwork.id,
            Artwork.title,
            Artwork.status,
            ST_Y(cast(Artwork.location, Geometry)).label("latitude"),
            ST_X(cast(Artwork.location, Geometry)).label("longitude"),
            Artwork.photo_count,
            func.coalesce(latest_photo.c.thumbnail_url, latest_photo.c.image_url).label("thumbnail_url"),
            func.ST_Distance(Artwork.location, ref_point).label("distance"),
        )
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(func.ST_DWithin(Artwork.location, ref_point, radius))
        .where(Artwork.is_deleted == False)  # noqa: E712
        .order_by(func.ST_Distance(Artwork.location, ref_point))
        .limit(20)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        ArtworkNearbyResponse(
            id=row.id,
            title=row.title,
            status=row.status,
            latitude=row.latitude,
            longitude=row.longitude,
            photo_count=row.photo_count,
            thumbnail_url=row.thumbnail_url,
        )
        for row in rows
    ]


@router.get("/{artwork_id}", response_model=ArtworkDetailResponse)
async def get_artwork_detail(
    artwork_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID | None = Depends(get_optional_user_id),
) -> ArtworkDetailResponse:
    """Get full artwork detail including all photos and creator info.

    Public endpoint. Returns artwork fields, artist name (if linked),
    creator display_name, and all photos ordered by date_taken ascending.
    """
    # Load artwork with relationships
    result = await db.execute(
        select(Artwork)
        .options(
            selectinload(Artwork.artist),
            selectinload(Artwork.created_by_user),
            selectinload(Artwork.photos).selectinload(Photo.user),
        )
        .where(Artwork.id == artwork_id, Artwork.is_deleted == False)  # noqa: E712
    )
    artwork = result.scalar_one_or_none()
    if artwork is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artwork not found")

    # Extract coordinates
    coord_query = select(
        ST_Y(cast(artwork.location, Geometry)).label("lat"),
        ST_X(cast(artwork.location, Geometry)).label("lng"),
    )
    coord_result = await db.execute(coord_query)
    coords = coord_result.one()

    # Build photo list ordered by date_taken ascending
    sorted_photos = sorted(
        [p for p in artwork.photos if not p.is_deleted],
        key=lambda p: (p.date_taken is None, p.date_taken),
    )

    photos = [
        PhotoDetailResponse(
            id=p.id,
            image_url=p.image_url,
            thumbnail_url=p.thumbnail_url,
            date_taken=p.date_taken,
            date_uploaded=p.date_uploaded,
            user_id=p.user_id,
            user_display_name=p.user.display_name,
            vote_count=p.vote_count,
            categories=p.categories or [],
        )
        for p in sorted_photos
    ]

    # Get suggestions summary
    suggestions = await _get_suggestion_summary(db, artwork_id)

    # Check if current user has favorited this artwork
    is_favorited = False
    if current_user_id is not None:
        fav_result = await db.execute(
            select(UserFavorite).where(
                UserFavorite.user_id == current_user_id,
                UserFavorite.artwork_id == artwork_id,
            )
        )
        is_favorited = fav_result.scalar_one_or_none() is not None

    return ArtworkDetailResponse(
        id=artwork.id,
        title=artwork.title,
        description=artwork.description,
        latitude=coords.lat,
        longitude=coords.lng,
        status=artwork.status,
        photo_count=artwork.photo_count,
        artist_id=artwork.artist_id,
        artist_name=artwork.artist.name if artwork.artist else None,
        created_by=artwork.created_by,
        creator_display_name=artwork.created_by_user.display_name,
        photos=photos,
        created_at=artwork.created_at,
        updated_at=artwork.updated_at,
        suggestions=suggestions,
        is_favorited=is_favorited,
    )


@router.get("/{artwork_id}/neighbors")
async def get_artwork_neighbors(
    artwork_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get previous and next artworks for navigation.

    Orders ALL artworks by creation date. Prev = the one before this in the list,
    Next = the one after. This creates a stable linear order with no loops.
    """
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

    base = (
        select(
            Artwork.id, Artwork.title,
            latest_photo.c.thumb.label("thumbnail_url"),
        )
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(Artwork.is_deleted == False)  # noqa: E712
    )

    # Get current artwork's created_at
    cur = await db.execute(
        select(Artwork.created_at).where(Artwork.id == artwork_id)
    )
    cur_row = cur.first()
    if cur_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artwork not found")
    current_created = cur_row.created_at

    # Prev = most recent artwork created BEFORE this one
    prev_q = base.where(Artwork.created_at < current_created).order_by(desc(Artwork.created_at)).limit(1)
    prev_row = (await db.execute(prev_q)).first()

    # Next = oldest artwork created AFTER this one
    next_q = base.where(Artwork.created_at > current_created).order_by(Artwork.created_at).limit(1)
    next_row = (await db.execute(next_q)).first()

    def _to_dict(r):
        return {"id": str(r.id), "title": r.title, "thumbnail_url": r.thumbnail_url} if r else None

    return {"prev": _to_dict(prev_row), "next": _to_dict(next_row)}


@router.get("/{artwork_id}/similar", response_model=list[SimilarArtworkItem])
async def get_similar_artworks(
    artwork_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SimilarArtworkItem]:
    """Get visually similar artworks based on CLIP embeddings.

    Computes the average embedding of all photos belonging to this artwork,
    then queries pgvector for the nearest photos from other artworks.
    Returns top 3 most similar artworks.
    """
    # Get all embeddings for photos of this artwork
    result = await db.execute(
        select(Photo.image_embedding).where(
            Photo.artwork_id == artwork_id,
            Photo.image_embedding.isnot(None),
        )
    )
    embeddings = [row[0] for row in result.all()]

    if not embeddings:
        return []

    # Compute average embedding
    import numpy as np

    avg_embedding = np.mean(embeddings, axis=0).tolist()

    # Subquery: find nearest photos from OTHER artworks
    cosine_dist = Photo.image_embedding.cosine_distance(avg_embedding)

    photo_query = (
        select(
            Photo.artwork_id,
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("photo_thumb"),
            (1 - cosine_dist).label("similarity"),
        )
        .where(
            Photo.artwork_id.isnot(None), Photo.is_deleted == False,  # noqa: E712
            Photo.artwork_id != artwork_id,
            Photo.image_embedding.isnot(None),
        )
        .order_by(cosine_dist)
        .limit(20)
        .subquery()
    )

    # Group by artwork_id, keep highest similarity
    grouped_query = (
        select(
            photo_query.c.artwork_id,
            func.max(photo_query.c.similarity).label("similarity"),
            func.max(photo_query.c.photo_thumb).label("thumbnail_url"),
        )
        .group_by(photo_query.c.artwork_id)
        .order_by(desc(func.max(photo_query.c.similarity)))
        .limit(3)
        .subquery()
    )

    # Join with Artwork for title
    final_query = select(
        grouped_query.c.artwork_id,
        Artwork.title,
        grouped_query.c.thumbnail_url,
        grouped_query.c.similarity,
    ).join(Artwork, Artwork.id == grouped_query.c.artwork_id)

    result = await db.execute(final_query)
    rows = result.all()

    return [
        SimilarArtworkItem(
            artwork_id=row.artwork_id,
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]


@router.get("/{artwork_id}/style-similar", response_model=list[StyleSimilarArtworkItem])
async def get_style_similar_artworks(
    artwork_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[StyleSimilarArtworkItem]:
    """Get artworks with similar artistic style based on style embeddings.

    Computes the average style embedding of all photos belonging to this artwork,
    then queries pgvector for the nearest artworks by style (excluding self).
    Returns top 5 most style-similar artworks.
    """
    import numpy as np

    # Get all style embeddings for photos of this artwork
    result = await db.execute(
        select(Photo.style_embedding).where(
            Photo.artwork_id == artwork_id,
            Photo.style_embedding.isnot(None),
        )
    )
    embeddings = [row[0] for row in result.all()]

    if not embeddings:
        return []

    # Compute average style embedding
    avg_embedding = np.mean(embeddings, axis=0).tolist()

    # Subquery: find nearest photos from OTHER artworks by style
    cosine_dist = Photo.style_embedding.cosine_distance(avg_embedding)

    photo_query = (
        select(
            Photo.artwork_id,
            func.coalesce(Photo.thumbnail_url, Photo.image_url).label("photo_thumb"),
            (1 - cosine_dist).label("similarity"),
        )
        .where(
            Photo.artwork_id.isnot(None), Photo.is_deleted == False,  # noqa: E712
            Photo.artwork_id != artwork_id,
            Photo.style_embedding.isnot(None),
        )
        .order_by(cosine_dist)
        .limit(30)
        .subquery()
    )

    # Group by artwork_id, keep highest similarity
    grouped_query = (
        select(
            photo_query.c.artwork_id,
            func.max(photo_query.c.similarity).label("similarity"),
            func.max(photo_query.c.photo_thumb).label("thumbnail_url"),
        )
        .group_by(photo_query.c.artwork_id)
        .order_by(desc(func.max(photo_query.c.similarity)))
        .limit(5)
        .subquery()
    )

    # Join with Artwork for title
    final_query = select(
        grouped_query.c.artwork_id,
        Artwork.title,
        grouped_query.c.thumbnail_url,
        grouped_query.c.similarity,
    ).join(Artwork, Artwork.id == grouped_query.c.artwork_id)

    result = await db.execute(final_query)
    rows = result.all()

    return [
        StyleSimilarArtworkItem(
            artwork_id=row.artwork_id,
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]


@router.get("", response_model=list[ArtworkMapItem])
@limiter.limit("30/minute")
async def list_artworks(
    request: Request,
    bounds: str | None = Query(None, description="Bounding box: south,west,north,east"),
    unattributed: bool = Query(False, description="If true, return only artworks with no artist"),
    db: AsyncSession = Depends(get_db),
) -> list[ArtworkMapItem]:
    """Return artworks for map view, optionally filtered by bounding box.

    Public endpoint (BE-6). If bounds parameter is provided, returns artworks
    within the bounding box using PostGIS ST_Within + ST_MakeEnvelope.
    Otherwise returns all artworks (most recent first). Limited to 500 results.
    Each result includes the most recent photo's image_url as thumbnail_url.
    """
    # Subquery to get most recent photo per artwork
    latest_photo_subq = (
        select(
            Photo.artwork_id,
            Photo.image_url,
            Photo.thumbnail_url,
            func.row_number()
            .over(partition_by=Photo.artwork_id, order_by=desc(Photo.date_taken).nullslast())
            .label("rn"),
        )
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False)  # noqa: E712
        .subquery()
    )
    latest_photo = (
        select(latest_photo_subq.c.artwork_id, latest_photo_subq.c.image_url, latest_photo_subq.c.thumbnail_url)
        .where(latest_photo_subq.c.rn == 1)
        .subquery()
    )

    # Base query
    query = select(
        Artwork.id,
        Artwork.title,
        Artwork.status,
        ST_Y(cast(Artwork.location, Geometry)).label("latitude"),
        ST_X(cast(Artwork.location, Geometry)).label("longitude"),
        Artwork.photo_count,
        func.coalesce(latest_photo.c.thumbnail_url, latest_photo.c.image_url).label("thumbnail_url"),
    ).outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id).where(
        Artwork.is_deleted == False  # noqa: E712
    )

    if bounds:
        # Parse bounding box: south,west,north,east
        try:
            parts = [float(x.strip()) for x in bounds.split(",")]
            if len(parts) != 4:
                raise ValueError("Expected 4 values")
            south, west, north, east = parts
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="bounds must be 4 comma-separated floats: south,west,north,east",
            )

        if not (-90 <= south <= 90) or not (-90 <= north <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude values (south, north) must be in [-90, 90]",
            )
        if not (-180 <= west <= 180) or not (-180 <= east <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude values (west, east) must be in [-180, 180]",
            )
        if south > north:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="south must be <= north",
            )

        # ST_MakeEnvelope(xmin, ymin, xmax, ymax, srid)
        # xmin=west, ymin=south, xmax=east, ymax=north
        envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)
        query = query.where(
            func.ST_Within(cast(Artwork.location, Geometry), envelope)
        )
    else:
        # No bounds: return most recent artworks
        query = query.order_by(desc(Artwork.created_at))

    if unattributed:
        query = query.where(Artwork.artist_id.is_(None))

    query = query.limit(500)

    result = await db.execute(query)
    rows = result.all()

    return [
        ArtworkMapItem(
            id=row.id,
            title=row.title,
            status=row.status,
            latitude=row.latitude,
            longitude=row.longitude,
            photo_count=row.photo_count,
            thumbnail_url=row.thumbnail_url,
        )
        for row in rows
    ]
