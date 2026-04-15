"""Artist detail and update endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Artist, ArtistSuggestion, Artwork, Photo, User, UserFollow
from app.schemas import (
    ArtistDetailResponse,
    ArtworkSummaryResponse,
    StyleSimilarArtistItem,
    UpdateArtistRequest,
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

router = APIRouter(prefix="/api/artists", tags=["artists"])


class ArtistListItem(BaseModel):
    id: uuid.UUID
    name: str
    bio: str | None = None
    artwork_count: int


@router.get("", response_model=list[ArtistListItem])
async def list_artists(
    db: AsyncSession = Depends(get_db),
) -> list[ArtistListItem]:
    """List all artists with actual artwork counts (confirmed + pending suggestions)."""
    # Count confirmed artworks + artworks with pending suggestions per artist
    confirmed_count = (
        select(func.count()).select_from(Artwork)
        .where(Artwork.artist_id == Artist.id, Artwork.is_deleted == False)  # noqa: E712
        .correlate(Artist)
        .scalar_subquery()
    )
    pending_count = (
        select(func.count(func.distinct(ArtistSuggestion.artwork_id)))
        .where(
            ArtistSuggestion.artist_id == Artist.id,
            ArtistSuggestion.status == "pending",
        )
        .correlate(Artist)
        .scalar_subquery()
    )
    total = confirmed_count + pending_count

    result = await db.execute(
        select(Artist, total.label("real_count"))
        .order_by(desc(total), Artist.name)
        .limit(100)
    )
    rows = result.all()
    return [
        ArtistListItem(
            id=row.Artist.id,
            name=row.Artist.name,
            bio=row.Artist.bio,
            artwork_count=row.real_count,
        )
        for row in rows
    ]


async def _build_artist_detail(
    artist: Artist,
    db: AsyncSession,
    current_user_id: uuid.UUID | None = None,
) -> ArtistDetailResponse:
    """Build a full ArtistDetailResponse including computed fields.

    Shared by GET and PATCH endpoints to avoid duplication.
    """
    artist_id = artist.id

    # Subquery: most recent photo per artwork (for thumbnails)
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

    # Query artworks: confirmed (artist_id set) OR pending suggestions for this artist
    pending_artwork_ids_subq = (
        select(ArtistSuggestion.artwork_id)
        .where(
            ArtistSuggestion.artist_id == artist_id,
            ArtistSuggestion.status == "pending",
        )
        .distinct()
        .subquery()
    )

    query = (
        select(
            Artwork.id,
            Artwork.title,
            Artwork.status,
            Artwork.photo_count,
            func.coalesce(latest_photo.c.thumbnail_url, latest_photo.c.image_url).label("thumbnail_url"),
        )
        .outerjoin(latest_photo, Artwork.id == latest_photo.c.artwork_id)
        .where(
            Artwork.is_deleted == False,  # noqa: E712
            (Artwork.artist_id == artist_id)
            | (Artwork.id.in_(select(pending_artwork_ids_subq)))
        )
        .order_by(desc(Artwork.created_at))
    )
    result = await db.execute(query)
    rows = result.all()

    artworks = [
        ArtworkSummaryResponse(
            id=row.id,
            title=row.title,
            status=row.status,
            thumbnail_url=row.thumbnail_url,
            photo_count=row.photo_count,
        )
        for row in rows
    ]

    # Compute total_photos across all artworks
    total_photos = sum(row.photo_count for row in rows)

    # Compute active_since (earliest artwork created_at)
    active_since_result = await db.execute(
        select(func.min(Artwork.created_at)).where(Artwork.artist_id == artist_id)
    )
    active_since = active_since_result.scalar_one()

    # Use actual count from query results instead of stale denormalized counter
    actual_artwork_count = len(rows)

    # Check if current user is following this artist
    is_following = False
    if current_user_id is not None:
        follow_result = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user_id,
                UserFollow.followed_artist_id == artist.id,
            )
        )
        is_following = follow_result.scalar_one_or_none() is not None

    return ArtistDetailResponse(
        id=artist.id,
        name=artist.name,
        bio=artist.bio,
        aliases=artist.aliases,
        website=artist.website,
        social_links=artist.social_links,
        artwork_count=actual_artwork_count,
        total_photos=total_photos,
        active_since=active_since,
        artworks=artworks,
        follower_count=artist.follower_count,
        is_following=is_following,
        claimed_by_user_id=str(artist.claimed_by_user_id) if artist.claimed_by_user_id else None,
        verified_at=artist.verified_at,
    )


@router.get("/{artist_id}", response_model=ArtistDetailResponse)
async def get_artist_detail(
    artist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID | None = Depends(get_optional_user_id),
) -> ArtistDetailResponse:
    """Get artist detail with list of attributed artworks.

    Public endpoint. Returns artist info including aliases, website,
    social_links, total_photos, active_since, plus a list of artworks
    attributed to this artist with photo_count and thumbnail.
    Includes follower_count and is_following (if authenticated).
    """
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found"
        )

    return await _build_artist_detail(artist, db, current_user_id)


@router.patch("/{artist_id}", response_model=ArtistDetailResponse)
async def update_artist(
    artist_id: uuid.UUID,
    body: UpdateArtistRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArtistDetailResponse:
    """Update an artist profile. Requires moderator or admin role.

    Accepts bio, website, social_links, and aliases fields.
    Returns the updated ArtistDetailResponse.
    """
    if current_user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only moderators and admins can update artist profiles",
        )

    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found"
        )

    if "bio" in body.model_fields_set:
        artist.bio = body.bio or None

    if "website" in body.model_fields_set:
        artist.website = body.website or None

    if "social_links" in body.model_fields_set:
        artist.social_links = body.social_links or None

    if "aliases" in body.model_fields_set:
        artist.aliases = body.aliases or None

    await db.commit()
    await db.refresh(artist)

    return await _build_artist_detail(artist, db)


@router.get("/{artist_id}/style-similar", response_model=list[StyleSimilarArtistItem])
async def get_style_similar_artists(
    artist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[StyleSimilarArtistItem]:
    """Get artists with similar artistic style based on style embeddings.

    Computes the average style embedding from all photos of this artist's artworks,
    then queries for the nearest artworks NOT by this artist, and groups by artist.
    Returns top 5 most style-similar artists.
    """
    import numpy as np

    # Verify artist exists
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found"
        )

    # Get all style embeddings for photos of this artist's artworks
    result = await db.execute(
        select(Photo.style_embedding)
        .join(Artwork, Photo.artwork_id == Artwork.id)
        .where(
            Artwork.artist_id == artist_id,
            Photo.style_embedding.isnot(None),
        )
    )
    embeddings = [row[0] for row in result.all()]

    if not embeddings:
        return []

    # Compute average style embedding
    avg_embedding = np.mean(embeddings, axis=0).tolist()

    # Find nearest photos from artworks NOT by this artist
    cosine_dist = Photo.style_embedding.cosine_distance(avg_embedding)

    photo_query = (
        select(
            Photo.artwork_id,
            (1 - cosine_dist).label("similarity"),
        )
        .where(
            Photo.artwork_id.isnot(None), Photo.is_deleted == False,  # noqa: E712
            Photo.style_embedding.isnot(None),
        )
        .order_by(cosine_dist)
        .limit(50)
        .subquery()
    )

    # Join with Artwork to get artist_id, exclude self
    artwork_query = (
        select(
            Artwork.artist_id,
            func.max(photo_query.c.similarity).label("similarity"),
        )
        .join(Artwork, Artwork.id == photo_query.c.artwork_id)
        .where(
            Artwork.artist_id.isnot(None),
            Artwork.artist_id != artist_id,
        )
        .group_by(Artwork.artist_id)
        .order_by(desc(func.max(photo_query.c.similarity)))
        .limit(5)
        .subquery()
    )

    # Join with Artist for name and artwork_count
    final_query = select(
        artwork_query.c.artist_id,
        Artist.name,
        Artist.artwork_count,
        artwork_query.c.similarity,
    ).join(Artist, Artist.id == artwork_query.c.artist_id)

    result = await db.execute(final_query)
    rows = result.all()

    return [
        StyleSimilarArtistItem(
            artist_id=row.artist_id,
            name=row.name,
            artwork_count=row.artwork_count,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]
