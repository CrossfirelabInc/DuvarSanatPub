"""Photo upload and image matching endpoints."""

import logging
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth import get_current_user
from app.clip_service import clip_service
from app.config import settings
from app.database import get_db
from app.models import Artwork, Photo, PhotoVote, User
from app.notification_utils import create_notification
from app.rate_limit import limiter
from app.schemas import LocationResponse, MatchResponse, MatchResultItem, PhotoResponse, SuggestTitleResponse, VoteResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/photos", tags=["photos"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

# Magic byte signatures for validating actual file content
MAGIC_BYTES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",  # WebP starts with RIFF
}

AUTO_MERGE_THRESHOLD = 0.95
THUMBNAIL_MAX_SIZE = 400


def _generate_thumbnail(content: bytes, upload_dir: Path, original_filename: str) -> str | None:
    """Generate a 400px max-dimension thumbnail and return its URL path."""
    try:
        from io import BytesIO

        img = Image.open(BytesIO(content))
        img.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE), Image.LANCZOS)

        thumb_dir = upload_dir / "thumbs"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        thumb_filename = f"thumb_{original_filename}"
        thumb_path = thumb_dir / thumb_filename
        img.save(str(thumb_path), quality=85, optimize=True)

        return f"/uploads/thumbs/{thumb_filename}"
    except Exception:
        logger.warning("Failed to generate thumbnail", exc_info=True)
        return None


def _detect_content_type(content: bytes) -> str | None:
    """Detect image content type from magic bytes.

    Returns the MIME type string if recognized, or None if the format
    is not supported.
    """
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_magic_bytes(content: bytes, content_type: str) -> None:
    """Validate that file content matches expected magic bytes for the claimed type.

    Raises HTTPException 400 if the actual file bytes do not match the
    expected signature for the given content type.
    """
    if content_type == "image/webp":
        if not (content[:4] == b"RIFF" and content[8:12] == b"WEBP"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match its declared type.",
            )
        return
    expected = MAGIC_BYTES.get(content_type)
    if expected is None or not content.startswith(expected):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its declared type. Upload a valid JPEG, PNG, or WebP.",
        )


@router.post("/upload", response_model=PhotoResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    date_taken: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """Upload a photo with location coordinates.

    Accepts multipart form data with an image file (JPEG/PNG/WebP, max 20MB),
    latitude, longitude, and optional date_taken (ISO format string).
    Creates a photo record with PostGIS point geometry.
    After saving, computes a CLIP embedding and stores it for image matching.

    If a very high-confidence match (>= 0.95 similarity) is found, the photo
    is automatically linked to that artwork (auto-merge). The response will
    include `auto_merged_artwork_id` so the frontend can skip artwork linking.
    """
    # Validate latitude / longitude ranges
    if not (-90 <= latitude <= 90):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Latitude must be between -90 and 90",
        )
    if not (-180 <= longitude <= 180):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Longitude must be between -180 and 180",
        )

    # Read file content and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit",
        )

    # Smart content-type detection: detect the real type from magic bytes
    real_type = _detect_content_type(content)
    if real_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Upload JPEG, PNG, or WebP.",
        )

    # Use detected type (handles cases like WebP files with wrong extension)
    content_type = real_type

    # NSFW content check using CLIP zero-shot classification
    if clip_service.is_loaded:
        try:
            is_safe, safety_score = clip_service.check_nsfw(content)
            if not is_safe:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This image has been flagged as potentially inappropriate content and cannot be uploaded.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("NSFW check failed, allowing upload", exc_info=True)

    # Parse optional date_taken
    parsed_date_taken: datetime | None = None
    if date_taken:
        try:
            parsed_date_taken = datetime.fromisoformat(date_taken)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_taken must be a valid ISO format datetime string",
            )

    # Determine file extension from detected content type
    ext = "jpg" if content_type == "image/jpeg" else ("png" if content_type == "image/png" else "webp")
    filename = f"{uuid.uuid4()}.{ext}"

    # Ensure upload directory exists
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Write file to local filesystem
    file_path = upload_dir / filename
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    image_url = f"/uploads/{filename}"

    # Generate thumbnail (400px max dimension)
    thumbnail_url = _generate_thumbnail(content, upload_dir, filename)

    # Compute CLIP embedding (graceful: if model not loaded, store NULL)
    embedding: list[float] | None = None
    if clip_service.is_loaded:
        try:
            embedding = clip_service.compute_embedding(content)
        except Exception:
            logger.warning("Failed to compute CLIP embedding for upload", exc_info=True)

    # Compute style embedding (graceful: if model not loaded or fails, store NULL)
    style_embedding: list[float] | None = None
    if clip_service.is_loaded:
        try:
            style_embedding = clip_service.compute_style_embedding(content)
        except Exception:
            logger.warning("Failed to compute style embedding", exc_info=True)

    # Create WKT point for PostGIS (note: WKT uses lng, lat order)
    wkt_point = f"SRID=4326;POINT({longitude} {latitude})"

    photo = Photo(
        user_id=current_user.id,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        location=wkt_point,
        date_taken=parsed_date_taken,
        image_embedding=embedding,
        style_embedding=style_embedding,
    )

    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    return PhotoResponse(
        id=photo.id,
        image_url=photo.image_url,
        location=LocationResponse(latitude=latitude, longitude=longitude),
        date_taken=photo.date_taken,
        date_uploaded=photo.date_uploaded,
        artwork_id=photo.artwork_id,
        auto_merged_artwork_id=None,
    )


@router.post("/match", response_model=MatchResponse)
@limiter.limit("20/minute")
async def match_photo(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    """Find artworks that visually match an uploaded image.

    Authenticated endpoint. Accepts a multipart image file (JPEG/PNG/WebP, max 20MB).
    Computes a CLIP embedding and queries pgvector for the nearest photo
    embeddings, grouped by artwork. Returns artworks with similarity >= 0.70,
    ordered by similarity descending, limited to 5 results.

    If the CLIP model is not loaded, returns an empty matches array.
    """
    # If model is not loaded, return empty gracefully
    if not clip_service.is_loaded:
        return MatchResponse(matches=[])

    # Read file content and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit",
        )

    # Smart content-type detection from magic bytes
    real_type = _detect_content_type(content)
    if real_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Upload JPEG, PNG, or WebP.",
        )

    # NSFW content check
    if clip_service.is_loaded:
        try:
            is_safe, safety_score = clip_service.check_nsfw(content)
            if not is_safe:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This image has been flagged as potentially inappropriate content and cannot be uploaded.",
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("NSFW check failed during match, continuing", exc_info=True)

    # Compute CLIP embedding of the query image
    try:
        query_embedding = clip_service.compute_embedding(content)
    except Exception:
        logger.warning("Failed to compute CLIP embedding for match query", exc_info=True)
        return MatchResponse(matches=[])

    # H5: Pass the embedding as a native Python list.
    # pgvector's SQLAlchemy integration handles binding it as a proper parameter,
    # avoiding string-formatted SQL injection vectors.
    embedding_list = query_embedding  # list[float] from clip_service

    # Subquery: find nearest photos with cosine distance, only those linked to artworks
    # cosine_distance returns (1 - cosine_similarity), so similarity = 1 - distance
    cosine_dist = Photo.image_embedding.cosine_distance(embedding_list)

    photo_query = (
        select(
            Photo.artwork_id,
            Photo.image_url.label("photo_image_url"),
            (1 - cosine_dist).label("similarity"),
        )
        .where(
            Photo.artwork_id.isnot(None), Photo.is_deleted == False,  # noqa: E712
            Photo.image_embedding.isnot(None),
        )
        .order_by(cosine_dist)
        .limit(20)
        .subquery()
    )

    # Group by artwork_id, keep highest similarity per artwork
    # Also join with Artwork to get title and location
    grouped_query = (
        select(
            photo_query.c.artwork_id,
            func.max(photo_query.c.similarity).label("similarity"),
            func.max(photo_query.c.photo_image_url).label("thumbnail_url"),
        )
        .group_by(photo_query.c.artwork_id)
        .having(func.max(photo_query.c.similarity) >= 0.70)
        .subquery()
    )

    # Join with Artwork to get title and coordinates
    final_query = (
        select(
            grouped_query.c.artwork_id,
            Artwork.title,
            grouped_query.c.thumbnail_url,
            ST_Y(cast(Artwork.location, Geometry)).label("latitude"),
            ST_X(cast(Artwork.location, Geometry)).label("longitude"),
            grouped_query.c.similarity,
        )
        .join(Artwork, Artwork.id == grouped_query.c.artwork_id)
        .order_by(desc(grouped_query.c.similarity))
        .limit(5)
    )

    result = await db.execute(final_query)
    rows = result.all()

    matches = [
        MatchResultItem(
            artwork_id=row.artwork_id,
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            latitude=row.latitude,
            longitude=row.longitude,
            similarity=round(float(row.similarity), 4),
        )
        for row in rows
    ]

    return MatchResponse(matches=matches)


@router.post("/{photo_id}/vote", response_model=VoteResponse)
async def toggle_vote(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VoteResponse:
    """Toggle a vote on a photo.

    If the user has already voted (category='overall'), the vote is removed.
    If not, a new vote is created. Users cannot vote on their own photos.
    Updates photos.vote_count and users.total_votes_received atomically.
    """
    # Fetch the photo
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
        )

    # Cannot vote on own photos
    if photo.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot vote on your own photos",
        )

    # Check if vote already exists
    existing_vote = await db.execute(
        select(PhotoVote).where(
            PhotoVote.user_id == current_user.id,
            PhotoVote.photo_id == photo_id,
            PhotoVote.category == "overall",
        )
    )
    vote = existing_vote.scalar_one_or_none()

    if vote is not None:
        # Remove vote
        await db.delete(vote)
        # Decrement counts
        await db.execute(
            update(Photo)
            .where(Photo.id == photo_id)
            .values(vote_count=Photo.vote_count - 1)
        )
        await db.execute(
            update(User)
            .where(User.id == photo.user_id)
            .values(total_votes_received=User.total_votes_received - 1)
        )
        await db.commit()

        # Refresh to get updated count
        await db.refresh(photo)
        return VoteResponse(voted=False, vote_count=photo.vote_count)
    else:
        # Create vote
        new_vote = PhotoVote(
            user_id=current_user.id,
            photo_id=photo_id,
            category="overall",
        )
        db.add(new_vote)
        # Increment counts
        await db.execute(
            update(Photo)
            .where(Photo.id == photo_id)
            .values(vote_count=Photo.vote_count + 1)
        )
        await db.execute(
            update(User)
            .where(User.id == photo.user_id)
            .values(total_votes_received=User.total_votes_received + 1)
        )
        await db.commit()

        await db.refresh(photo)
        return VoteResponse(voted=True, vote_count=photo.vote_count)


@router.post("/{photo_id}/downvote", response_model=VoteResponse)
async def toggle_downvote(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VoteResponse:
    """Toggle a downvote on a photo.

    If the user has already downvoted (category='downvote'), the downvote is removed.
    If not, a new downvote is created. Users cannot downvote their own photos.
    Updates photos.downvote_count atomically.
    The downvote count is never exposed to regular users — it is only used
    internally for community filtering and moderator review.
    """
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found"
        )

    if photo.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot downvote your own photos",
        )

    existing_vote = await db.execute(
        select(PhotoVote).where(
            PhotoVote.user_id == current_user.id,
            PhotoVote.photo_id == photo_id,
            PhotoVote.category == "downvote",
        )
    )
    vote = existing_vote.scalar_one_or_none()

    if vote is not None:
        await db.delete(vote)
        await db.execute(
            update(Photo)
            .where(Photo.id == photo_id)
            .values(downvote_count=Photo.downvote_count - 1)
        )
        await db.commit()
        await db.refresh(photo)
        # Return vote_count (upvotes) — downvote_count is never exposed
        return VoteResponse(voted=False, vote_count=photo.vote_count)
    else:
        new_vote = PhotoVote(
            user_id=current_user.id,
            photo_id=photo_id,
            category="downvote",
        )
        db.add(new_vote)
        await db.execute(
            update(Photo)
            .where(Photo.id == photo_id)
            .values(downvote_count=Photo.downvote_count + 1)
        )
        await db.commit()
        await db.refresh(photo)
        return VoteResponse(voted=True, vote_count=photo.vote_count)


@router.post("/suggest-title", response_model=SuggestTitleResponse)
@limiter.limit("5/minute")
async def suggest_title(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> SuggestTitleResponse:
    """Suggest an artwork title from image content.

    Accepts an image file and returns a short caption
    that can be used as an artwork title. The suggestion is optional —
    the user may ignore it.
    """
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 20MB limit",
        )

    real_type = _detect_content_type(content)
    if real_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Upload JPEG, PNG, or WebP.",
        )

    if not clip_service.is_loaded:
        return SuggestTitleResponse(suggested_title=None)

    title = clip_service.suggest_title(content)
    return SuggestTitleResponse(suggested_title=title)
