"""Moderation endpoints: artist claims, claim review, user promotion, content flags, user bans."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, ArtistClaim, Artwork, Comment, ContentFlag, ModerationLog, Photo, User
from app.notification_utils import create_notification
from app.schemas import (
    BanUserRequest,
    ClaimResponse,
    CreateClaimRequest,
    CreateFlagRequest,
    FlagResponse,
    PromoteRequest,
    RejectClaimRequest,
    ReviewFlagRequest,
    UserResponse,
)
from sqlalchemy import update, func, delete

router = APIRouter(tags=["moderation"])


def _require_moderator(user: User) -> None:
    """Raise 403 if user is not a moderator or admin."""
    if user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or admin role required",
        )


def _require_admin(user: User) -> None:
    """Raise 403 if user is not an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


def _claim_to_response(claim: ArtistClaim, artist_name: str | None = None, claimant_name: str | None = None) -> ClaimResponse:
    """Convert an ArtistClaim model to a ClaimResponse."""
    return ClaimResponse(
        id=claim.id,
        user_id=claim.user_id,
        artist_id=claim.artist_id,
        verification_text=claim.verification_text,
        verification_url=claim.verification_url,
        status=claim.status,
        reviewed_by=claim.reviewed_by,
        review_note=claim.review_note,
        created_at=claim.created_at,
        reviewed_at=claim.reviewed_at,
        artist_name=artist_name,
        claimant_display_name=claimant_name,
    )


# POST /api/artists/:id/claim — Submit a claim


@router.post("/api/artists/{artist_id}/claim", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    artist_id: uuid.UUID,
    body: CreateClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """Submit a claim to be verified as a particular artist.

    Returns 409 if the artist is already claimed or the user already has a
    pending claim for this artist.
    """
    # Check artist exists
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found")

    # Check if already claimed
    if artist.claimed_by_user_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Artist is already claimed")

    # Check for existing pending claim by this user
    existing = await db.execute(
        select(ArtistClaim).where(
            ArtistClaim.user_id == current_user.id,
            ArtistClaim.artist_id == artist_id,
            ArtistClaim.status == "pending",
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a pending claim for this artist")

    claim = ArtistClaim(
        user_id=current_user.id,
        artist_id=artist_id,
        verification_text=body.verification_text,
        verification_url=body.verification_url,
        status="pending",
    )
    db.add(claim)

    # Notify all moderators and admins
    mod_result = await db.execute(
        select(User.id).where(User.role.in_(["moderator", "admin"]))
    )
    mod_ids = [row[0] for row in mod_result.all()]
    for mod_id in mod_ids:
        await create_notification(
            db,
            user_id=mod_id,
            type="new_claim",
            title=f"New artist claim: {artist.name}",
            message=f"Claimed by {current_user.display_name}",
            link="/mod",
        )

    await db.commit()
    await db.refresh(claim)

    return _claim_to_response(claim, artist_name=artist.name, claimant_name=current_user.display_name)


# GET /api/mod/claims — List claims (moderator/admin only)


@router.get("/api/mod/claims", response_model=list[ClaimResponse])
async def list_claims(
    status_filter: str = "pending",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClaimResponse]:
    """List artist claims filtered by status. Requires moderator or admin role."""
    _require_moderator(current_user)

    if status_filter not in ("pending", "approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be one of: pending, approved, rejected",
        )

    result = await db.execute(
        select(ArtistClaim, Artist.name, User.display_name)
        .join(Artist, ArtistClaim.artist_id == Artist.id)
        .join(User, ArtistClaim.user_id == User.id)
        .where(ArtistClaim.status == status_filter)
        .order_by(ArtistClaim.created_at)
    )
    rows = result.all()

    return [
        _claim_to_response(row[0], artist_name=row[1], claimant_name=row[2])
        for row in rows
    ]


# POST /api/mod/claims/:id/approve — Approve a claim


@router.post("/api/mod/claims/{claim_id}/approve", response_model=ClaimResponse)
async def approve_claim(
    claim_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """Approve a pending artist claim. Sets artist as verified and claimed."""
    _require_moderator(current_user)

    result = await db.execute(select(ArtistClaim).where(ArtistClaim.id == claim_id))
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    if claim.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Claim is not pending")

    now = datetime.now(timezone.utc)

    # Update claim
    claim.status = "approved"
    claim.reviewed_by = current_user.id
    claim.reviewed_at = now

    # Update artist
    artist_result = await db.execute(select(Artist).where(Artist.id == claim.artist_id))
    artist = artist_result.scalar_one_or_none()
    if artist is not None:
        artist.verified_at = now
        artist.claimed_by_user_id = claim.user_id

    # Get claimant name
    user_result = await db.execute(select(User).where(User.id == claim.user_id))
    claimant = user_result.scalar_one_or_none()

    # Notify the claimant
    await create_notification(
        db,
        user_id=claim.user_id,
        type="claim_approved",
        title="Artist claim approved",
        message=f"Your claim for artist '{artist.name}' has been approved!" if artist else "Your artist claim has been approved!",
        link=f"/artists/{claim.artist_id}",
    )

    await db.commit()
    await db.refresh(claim)

    return _claim_to_response(
        claim,
        artist_name=artist.name if artist else None,
        claimant_name=claimant.display_name if claimant else None,
    )


# POST /api/mod/claims/:id/reject — Reject a claim


@router.post("/api/mod/claims/{claim_id}/reject", response_model=ClaimResponse)
async def reject_claim(
    claim_id: uuid.UUID,
    body: RejectClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """Reject a pending artist claim with optional review note."""
    _require_moderator(current_user)

    result = await db.execute(select(ArtistClaim).where(ArtistClaim.id == claim_id))
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    if claim.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Claim is not pending")

    claim.status = "rejected"
    claim.reviewed_by = current_user.id
    claim.reviewed_at = datetime.now(timezone.utc)
    if body.note:
        claim.review_note = body.note

    # Get artist and claimant names
    artist_result = await db.execute(select(Artist).where(Artist.id == claim.artist_id))
    artist = artist_result.scalar_one_or_none()
    user_result = await db.execute(select(User).where(User.id == claim.user_id))
    claimant = user_result.scalar_one_or_none()

    # Notify the claimant
    await create_notification(
        db,
        user_id=claim.user_id,
        type="claim_rejected",
        title="Artist claim rejected",
        message=f"Your claim for artist '{artist.name}' was not approved." if artist else "Your artist claim was not approved.",
        link=f"/artists/{claim.artist_id}",
    )

    await db.commit()
    await db.refresh(claim)

    return _claim_to_response(
        claim,
        artist_name=artist.name if artist else None,
        claimant_name=claimant.display_name if claimant else None,
    )


# POST /api/admin/promote — Promote a user's role


@router.post("/api/admin/promote", response_model=UserResponse)
async def promote_user(
    body: PromoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Promote a user to moderator or admin. Requires admin role."""
    _require_admin(current_user)

    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = body.role
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


# Auto-merge duplicate artworks (moderator/admin tool)

MERGE_SIMILARITY_THRESHOLD = 0.95


@router.post("/api/mod/merge-duplicates")
async def merge_duplicate_artworks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find and merge duplicate artworks based on CLIP similarity.

    Moderator/admin only. Finds pairs of artworks whose photos have >= 95%
    cosine similarity. Merges the newer artwork into the older one:
    - Moves all photos from newer to older
    - Moves comments from newer to older
    - Keeps the artist attribution from whichever has one (or the older one)
    - Deletes the newer artwork
    """
    _require_moderator(current_user)

    # Find all photo pairs with high similarity across different artworks
    from app.models import ArtistSuggestion

    # Get all photos with embeddings that are linked to artworks
    photo_result = await db.execute(
        select(Photo.id, Photo.artwork_id, Photo.image_embedding)
        .where(Photo.artwork_id.isnot(None), Photo.is_deleted == False, Photo.image_embedding.isnot(None))  # noqa: E712
    )
    photos = photo_result.all()

    if len(photos) < 2:
        return {"merges": 0, "message": "Not enough photos to compare"}

    # Group photos by artwork
    artwork_photos: dict[str, list] = {}
    for p in photos:
        aid = str(p.artwork_id)
        if aid not in artwork_photos:
            artwork_photos[aid] = []
        artwork_photos[aid].append(p)

    # Compare artworks pairwise using their first photo's embedding
    merge_pairs: list[tuple[str, str]] = []  # (keep_id, merge_id)
    artwork_ids = list(artwork_photos.keys())
    merged_set: set[str] = set()

    for i in range(len(artwork_ids)):
        if artwork_ids[i] in merged_set:
            continue
        for j in range(i + 1, len(artwork_ids)):
            if artwork_ids[j] in merged_set:
                continue

            # Compare first photo of each artwork
            emb_a = artwork_photos[artwork_ids[i]][0].image_embedding
            emb_b = artwork_photos[artwork_ids[j]][0].image_embedding

            if emb_a is None or emb_b is None:
                continue

            # Compute cosine similarity
            import numpy as np
            a = np.array(emb_a)
            b = np.array(emb_b)
            similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

            if similarity >= MERGE_SIMILARITY_THRESHOLD:
                # Decide which to keep (older = lower created_at)
                aw_a = await db.execute(select(Artwork).where(Artwork.id == artwork_ids[i]))
                aw_b = await db.execute(select(Artwork).where(Artwork.id == artwork_ids[j]))
                art_a = aw_a.scalar_one_or_none()
                art_b = aw_b.scalar_one_or_none()

                if not art_a or not art_b:
                    continue

                # Smart merge rules:
                # If both have different confirmed artists → skip (different artworks)
                if (art_a.artist_id and art_b.artist_id
                        and art_a.artist_id != art_b.artist_id):
                    continue

                # Keep the one with the artist, or the older one
                if art_b.artist_id and not art_a.artist_id:
                    keep, remove = art_b, art_a
                else:
                    keep, remove = art_a, art_b

                merge_pairs.append((str(keep.id), str(remove.id)))
                merged_set.add(str(remove.id))

    # Execute merges
    merges_done = 0
    for keep_id, remove_id in merge_pairs:
        # Move photos from remove to keep
        await db.execute(
            update(Photo)
            .where(Photo.artwork_id == remove_id)
            .values(artwork_id=keep_id)
        )

        # Move comments from remove to keep
        await db.execute(
            update(Comment)
            .where(Comment.target_type == "artwork", Comment.target_id == remove_id)
            .values(target_id=keep_id)
        )

        # Update photo count on keep
        photo_count = await db.scalar(
            select(func.count()).select_from(Photo).where(Photo.artwork_id == keep_id)
        )
        await db.execute(
            update(Artwork).where(Artwork.id == keep_id).values(photo_count=photo_count)
        )

        # Delete the duplicate artwork
        # First clean up any references
        await db.execute(
            delete(ArtistSuggestion).where(ArtistSuggestion.artwork_id == remove_id)
        )
        await db.execute(delete(Artwork).where(Artwork.id == remove_id))

        merges_done += 1

    await db.commit()

    return {
        "merges": merges_done,
        "message": f"Merged {merges_done} duplicate artwork(s)",
    }


# Content Flags


@router.post("/api/flags", response_model=FlagResponse, status_code=status.HTTP_201_CREATED)
async def create_flag(
    body: CreateFlagRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlagResponse:
    """Flag/report content. Users cannot flag their own content."""
    if current_user.banned_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")

    # Prevent self-flagging for user targets
    if body.target_type == "user" and body.target_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot flag yourself")

    # Check for duplicate flag from same user on same target
    existing = await db.execute(
        select(ContentFlag).where(
            ContentFlag.reporter_id == current_user.id,
            ContentFlag.target_type == body.target_type,
            ContentFlag.target_id == body.target_id,
            ContentFlag.status == "pending",
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already flagged this content",
        )

    flag = ContentFlag(
        reporter_id=current_user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
        description=body.description,
    )
    db.add(flag)

    # Notify all moderators and admins
    mod_result = await db.execute(
        select(User.id).where(User.role.in_(["moderator", "admin"]))
    )
    mod_ids = [row[0] for row in mod_result.all()]
    for mod_id in mod_ids:
        await create_notification(
            db,
            user_id=mod_id,
            type="new_flag",
            title=f"New {body.reason} report on {body.target_type}",
            message=f"Reported by {current_user.display_name}",
            link="/mod",
        )

    await db.commit()
    await db.refresh(flag)

    return FlagResponse(
        id=flag.id,
        reporter_id=flag.reporter_id,
        target_type=flag.target_type,
        target_id=flag.target_id,
        reason=flag.reason,
        description=flag.description,
        status=flag.status,
        created_at=flag.created_at,
        reporter_display_name=current_user.display_name,
    )


@router.get("/api/mod/flags", response_model=list[FlagResponse])
async def list_flags(
    flag_status: str = Query("pending", pattern="^(pending|actioned|dismissed)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FlagResponse]:
    """List content flags filtered by status. Moderator+ only."""
    _require_moderator(current_user)

    result = await db.execute(
        select(ContentFlag, User.display_name)
        .join(User, User.id == ContentFlag.reporter_id)
        .where(ContentFlag.status == flag_status)
        .order_by(desc(ContentFlag.created_at))
        .limit(50)
    )
    rows = result.all()

    return [
        FlagResponse(
            id=flag.id,
            reporter_id=flag.reporter_id,
            target_type=flag.target_type,
            target_id=flag.target_id,
            reason=flag.reason,
            description=flag.description,
            status=flag.status,
            reviewed_by=flag.reviewed_by,
            review_note=flag.review_note,
            created_at=flag.created_at,
            reviewed_at=flag.reviewed_at,
            reporter_display_name=display_name,
        )
        for flag, display_name in rows
    ]


TARGET_MODELS = {"photo": Photo, "comment": Comment, "artwork": Artwork}


@router.post("/api/mod/flags/{flag_id}/review", response_model=FlagResponse)
async def review_flag(
    flag_id: uuid.UUID,
    body: ReviewFlagRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlagResponse:
    """Review a content flag. Moderator+ only.

    action='delete' soft-deletes the flagged content and creates an audit log entry.
    action='dismissed' marks the flag as dismissed (no action taken).
    """
    _require_moderator(current_user)

    result = await db.execute(select(ContentFlag).where(ContentFlag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found")

    if flag.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flag already reviewed")

    now = datetime.now(timezone.utc)

    if body.action == "delete":
        # Soft-delete the target content
        model = TARGET_MODELS.get(flag.target_type)
        if model:
            target_result = await db.execute(select(model).where(model.id == flag.target_id))
            target = target_result.scalar_one_or_none()
            if target and hasattr(target, "is_deleted"):
                target.is_deleted = True

                # If a photo was deleted, check if its artwork has zero remaining photos
                if flag.target_type == "photo" and hasattr(target, "artwork_id") and target.artwork_id:
                    remaining = await db.scalar(
                        select(func.count()).select_from(Photo).where(
                            Photo.artwork_id == target.artwork_id,
                            Photo.is_deleted == False,  # noqa: E712
                            Photo.id != target.id,
                        )
                    )
                    if remaining == 0:
                        artwork_result = await db.execute(
                            select(Artwork).where(Artwork.id == target.artwork_id)
                        )
                        artwork = artwork_result.scalar_one_or_none()
                        if artwork:
                            artwork.is_deleted = True

        # Create audit log
        log_entry = ModerationLog(
            moderator_id=current_user.id,
            action=f"delete_{flag.target_type}",
            target_type=flag.target_type,
            target_id=flag.target_id,
            flag_id=flag.id,
            reason=body.note or flag.reason,
        )
        db.add(log_entry)
        flag.status = "actioned"
    else:
        flag.status = "dismissed"

    flag.reviewed_by = current_user.id
    flag.review_note = body.note
    flag.reviewed_at = now

    await db.commit()
    await db.refresh(flag)

    return FlagResponse(
        id=flag.id,
        reporter_id=flag.reporter_id,
        target_type=flag.target_type,
        target_id=flag.target_id,
        reason=flag.reason,
        description=flag.description,
        status=flag.status,
        reviewed_by=flag.reviewed_by,
        review_note=flag.review_note,
        created_at=flag.created_at,
        reviewed_at=flag.reviewed_at,
    )


@router.get("/api/mod/audit-log")
async def get_audit_log(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get moderation audit log. Admin only."""
    _require_admin(current_user)

    result = await db.execute(
        select(ModerationLog, User.display_name)
        .join(User, User.id == ModerationLog.moderator_id)
        .order_by(desc(ModerationLog.created_at))
        .limit(100)
    )
    rows = result.all()

    return [
        {
            "id": str(log.id),
            "moderator_name": display_name,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": str(log.target_id),
            "flag_id": str(log.flag_id) if log.flag_id else None,
            "reason": log.reason,
            "reverted": log.reverted_at is not None,
            "created_at": log.created_at.isoformat(),
        }
        for log, display_name in rows
    ]


@router.post("/api/mod/audit-log/{log_id}/revert")
async def revert_mod_action(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revert a moderation action (restore soft-deleted content). Admin only."""
    _require_admin(current_user)

    result = await db.execute(select(ModerationLog).where(ModerationLog.id == log_id))
    log_entry = result.scalar_one_or_none()
    if log_entry is None:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    if log_entry.reverted_at is not None:
        raise HTTPException(status_code=400, detail="Action already reverted")

    # Restore the soft-deleted content
    model = TARGET_MODELS.get(log_entry.target_type)
    if model:
        target_result = await db.execute(select(model).where(model.id == log_entry.target_id))
        target = target_result.scalar_one_or_none()
        if target and hasattr(target, "is_deleted"):
            target.is_deleted = False

            # If restoring a photo, also restore its artwork if it was auto-deleted
            if log_entry.target_type == "photo" and hasattr(target, "artwork_id") and target.artwork_id:
                artwork_result = await db.execute(
                    select(Artwork).where(Artwork.id == target.artwork_id)
                )
                artwork = artwork_result.scalar_one_or_none()
                if artwork and artwork.is_deleted:
                    artwork.is_deleted = False

    log_entry.reverted_at = datetime.now(timezone.utc)
    log_entry.reverted_by = current_user.id

    await db.commit()

    return {"status": "reverted", "target_type": log_entry.target_type, "target_id": str(log_entry.target_id)}


# User Bans


@router.post("/api/mod/ban", response_model=UserResponse)
async def ban_user(
    body: BanUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Ban a user. Moderator+ only. Cannot ban admins."""
    _require_moderator(current_user)

    result = await db.execute(select(User).where(User.id == body.user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.role == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot ban an admin")

    if target.banned_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already banned")

    target.banned_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(target)

    return UserResponse.model_validate(target)


@router.post("/api/mod/unban", response_model=UserResponse)
async def unban_user(
    body: BanUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Unban a user. Moderator+ only."""
    _require_moderator(current_user)

    result = await db.execute(select(User).where(User.id == body.user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.banned_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not banned")

    target.banned_at = None
    await db.commit()
    await db.refresh(target)

    return UserResponse.model_validate(target)
