"""Challenge listing and progress-check endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import (
    ArtistSuggestion,
    Artwork,
    Challenge,
    ChallengeProgress,
    Neighborhood,
    Photo,
    User,
    UserBadge,
)
from app.notification_utils import create_notification
from app.schemas import ChallengeProgressResponse, ChallengeResponse

router = APIRouter(prefix="/api/challenges", tags=["challenges"])

optional_bearer = HTTPBearer(auto_error=False)


async def _get_optional_user_id(
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


@router.get("", response_model=list[ChallengeResponse])
async def list_challenges(
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID | None = Depends(_get_optional_user_id),
) -> list[ChallengeResponse]:
    """List all active challenges with optional user progress.

    Public endpoint. If the caller is authenticated, each challenge includes
    the user's current progress, target, and completed status.
    """
    result = await db.execute(
        select(Challenge).where(Challenge.is_active.is_(True)).order_by(Challenge.created_at)
    )
    challenges = result.scalars().all()

    # Load progress for authenticated user
    progress_map: dict[uuid.UUID, ChallengeProgress] = {}
    if current_user_id is not None:
        prog_result = await db.execute(
            select(ChallengeProgress).where(ChallengeProgress.user_id == current_user_id)
        )
        for p in prog_result.scalars().all():
            progress_map[p.challenge_id] = p

    items: list[ChallengeResponse] = []
    for c in challenges:
        p = progress_map.get(c.id)
        target = c.criteria.get("count", 1) if isinstance(c.criteria, dict) else 1
        items.append(
            ChallengeResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                challenge_type=c.challenge_type,
                badge_type=c.badge_type,
                progress=p.progress if p else 0,
                target=p.target if p else target,
                completed=p.completed_at is not None if p else False,
            )
        )
    return items


async def _compute_progress(
    db: AsyncSession, user_id: uuid.UUID, challenge: Challenge
) -> int:
    """Compute the user's current progress for a challenge based on criteria.

    Returns the raw count of qualifying actions the user has performed.
    """
    criteria = challenge.criteria if isinstance(challenge.criteria, dict) else {}
    action = criteria.get("action", "")

    if action == "suggest_artist":
        # Count distinct artworks user has suggested artists for
        result = await db.scalar(
            select(func.count(distinct(ArtistSuggestion.artwork_id))).where(
                ArtistSuggestion.suggested_by == user_id
            )
        )
        return result or 0

    elif action == "upload_category":
        # Count photos with the specified category
        category = criteria.get("category", "")
        result = await db.scalar(
            select(func.count()).select_from(Photo).where(
                Photo.user_id == user_id,
                Photo.categories.any(category),
            )
        )
        return result or 0

    elif action == "upload_neighborhoods":
        # Count distinct neighborhoods the user has uploaded photos to
        result = await db.scalar(
            select(func.count(distinct(Artwork.neighborhood_id))).where(
                Photo.user_id == user_id,
                Photo.artwork_id == Artwork.id,
                Artwork.neighborhood_id.isnot(None),
            )
        )
        return result or 0

    elif action == "seasonal_pair":
        # Count artworks where user has photos in 2+ different seasons
        # Simplified: count artworks with 2+ photos by this user
        from sqlalchemy import and_

        subq = (
            select(Photo.artwork_id, func.count().label("cnt"))
            .where(
                Photo.user_id == user_id,
                Photo.artwork_id.isnot(None), Photo.is_deleted == False,  # noqa: E712
            )
            .group_by(Photo.artwork_id)
            .having(func.count() >= 2)
            .subquery()
        )
        result = await db.scalar(select(func.count()).select_from(subq))
        return result or 0

    elif action == "first_photo":
        # Count artworks where the user's photo was the first one
        # (i.e., user created the artwork)
        result = await db.scalar(
            select(func.count()).select_from(Artwork).where(
                Artwork.created_by == user_id,
                Artwork.photo_count >= 1,
            )
        )
        return result or 0

    return 0


@router.post("/check-all", response_model=list[ChallengeProgressResponse])
async def check_all_challenges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChallengeProgressResponse]:
    """Check and update progress for ALL active challenges at once."""
    result = await db.execute(
        select(Challenge).where(Challenge.is_active.is_(True))
    )
    challenges = result.scalars().all()

    results = []
    for challenge in challenges:
        criteria = challenge.criteria if isinstance(challenge.criteria, dict) else {}
        target = criteria.get("count", 1)

        prog_result = await db.execute(
            select(ChallengeProgress).where(
                ChallengeProgress.challenge_id == challenge.id,
                ChallengeProgress.user_id == current_user.id,
            )
        )
        progress_record = prog_result.scalar_one_or_none()

        if progress_record is not None and progress_record.completed_at is not None:
            results.append(ChallengeProgressResponse(
                challenge_id=challenge.id,
                progress=progress_record.progress,
                target=progress_record.target,
                completed=True,
                badge_awarded=False,
            ))
            continue

        current_progress = await _compute_progress(db, current_user.id, challenge)
        capped_progress = min(current_progress, target)

        if progress_record is None:
            progress_record = ChallengeProgress(
                challenge_id=challenge.id,
                user_id=current_user.id,
                progress=capped_progress,
                target=target,
            )
            db.add(progress_record)
        else:
            progress_record.progress = capped_progress

        badge_awarded = False
        if capped_progress >= target and progress_record.completed_at is None:
            progress_record.completed_at = datetime.now(timezone.utc)
            existing_badge = await db.execute(
                select(UserBadge).where(
                    UserBadge.user_id == current_user.id,
                    UserBadge.badge_type == challenge.badge_type,
                )
            )
            if existing_badge.scalar_one_or_none() is None:
                db.add(UserBadge(user_id=current_user.id, badge_type=challenge.badge_type))
                badge_awarded = True
                await create_notification(
                    db,
                    user_id=current_user.id,
                    type="badge_earned",
                    title=f"Badge earned: {challenge.title}",
                    message=f"You completed the '{challenge.title}' challenge and earned the {challenge.badge_type} badge!",
                    link="/community",
                )

        results.append(ChallengeProgressResponse(
            challenge_id=challenge.id,
            progress=capped_progress,
            target=target,
            completed=progress_record.completed_at is not None,
            badge_awarded=badge_awarded,
        ))

    await db.commit()
    return results


@router.post("/{challenge_id}/check", response_model=ChallengeProgressResponse)
async def check_challenge_progress(
    challenge_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChallengeProgressResponse:
    """Check and update the user's progress for a specific challenge.

    Queries the user's activity based on challenge criteria, updates
    the challenge_progress record, and awards a badge if the target is reached.
    """
    # Fetch challenge
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")

    if not challenge.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge is not active"
        )

    criteria = challenge.criteria if isinstance(challenge.criteria, dict) else {}
    target = criteria.get("count", 1)

    # Get or create progress record
    prog_result = await db.execute(
        select(ChallengeProgress).where(
            ChallengeProgress.challenge_id == challenge_id,
            ChallengeProgress.user_id == current_user.id,
        )
    )
    progress_record = prog_result.scalar_one_or_none()

    if progress_record is not None and progress_record.completed_at is not None:
        # Already completed
        return ChallengeProgressResponse(
            challenge_id=challenge_id,
            progress=progress_record.progress,
            target=progress_record.target,
            completed=True,
            badge_awarded=False,
        )

    # Compute current progress
    current_progress = await _compute_progress(db, current_user.id, challenge)
    capped_progress = min(current_progress, target)

    if progress_record is None:
        progress_record = ChallengeProgress(
            challenge_id=challenge_id,
            user_id=current_user.id,
            progress=capped_progress,
            target=target,
        )
        db.add(progress_record)
    else:
        progress_record.progress = capped_progress

    badge_awarded = False

    # Check if target reached
    if capped_progress >= target and progress_record.completed_at is None:
        progress_record.completed_at = datetime.now(timezone.utc)

        # Award badge if not already awarded
        existing_badge = await db.execute(
            select(UserBadge).where(
                UserBadge.user_id == current_user.id,
                UserBadge.badge_type == challenge.badge_type,
            )
        )
        if existing_badge.scalar_one_or_none() is None:
            badge = UserBadge(
                user_id=current_user.id,
                badge_type=challenge.badge_type,
            )
            db.add(badge)
            badge_awarded = True

            # Create notification
            await create_notification(
                db,
                user_id=current_user.id,
                type="badge_earned",
                title=f"Badge earned: {challenge.title}",
                message=f"You completed the '{challenge.title}' challenge and earned the {challenge.badge_type} badge!",
                link="/community",
            )

    await db.commit()
    await db.refresh(progress_record)

    return ChallengeProgressResponse(
        challenge_id=challenge_id,
        progress=progress_record.progress,
        target=progress_record.target,
        completed=progress_record.completed_at is not None,
        badge_awarded=badge_awarded,
    )
