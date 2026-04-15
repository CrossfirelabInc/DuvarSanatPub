"""Follow/unfollow endpoints for artists and users."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, User, UserFollow
from app.schemas import (
    FollowerCountResponse,
    FollowingArtistItem,
    FollowingListResponse,
    FollowingUserItem,
    FollowResponse,
)

router = APIRouter(tags=["follows"])


# POST /api/artists/:id/follow — toggle follow on an artist


@router.post("/api/artists/{artist_id}/follow", response_model=FollowResponse)
async def toggle_follow_artist(
    artist_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    """Toggle follow on an artist.

    If already following, unfollow (delete row, decrement artist.follower_count).
    If not following, follow (create row, increment artist.follower_count).
    """
    # Verify artist exists
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found"
        )

    # Check existing follow
    existing = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.followed_artist_id == artist_id,
        )
    )
    follow = existing.scalar_one_or_none()

    if follow is not None:
        # Unfollow
        await db.delete(follow)
        await db.execute(
            update(Artist)
            .where(Artist.id == artist_id)
            .values(follower_count=Artist.follower_count - 1)
        )
        await db.commit()
        await db.refresh(artist)
        return FollowResponse(following=False, follower_count=artist.follower_count)
    else:
        # Follow
        new_follow = UserFollow(
            follower_id=current_user.id,
            followed_artist_id=artist_id,
        )
        db.add(new_follow)
        await db.execute(
            update(Artist)
            .where(Artist.id == artist_id)
            .values(follower_count=Artist.follower_count + 1)
        )
        await db.commit()
        await db.refresh(artist)
        return FollowResponse(following=True, follower_count=artist.follower_count)


# POST /api/users/:id/follow — toggle follow on a user


@router.post("/api/users/{user_id}/follow", response_model=FollowResponse)
async def toggle_follow_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    """Toggle follow on a user.

    Cannot follow yourself (400). Otherwise same toggle logic as artist follow.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself",
        )

    # Verify target user exists
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check existing follow
    existing = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.followed_user_id == user_id,
        )
    )
    follow = existing.scalar_one_or_none()

    if follow is not None:
        # Unfollow
        await db.delete(follow)
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(follower_count=User.follower_count - 1)
        )
        await db.commit()
        await db.refresh(target_user)
        return FollowResponse(following=False, follower_count=target_user.follower_count)
    else:
        # Follow
        new_follow = UserFollow(
            follower_id=current_user.id,
            followed_user_id=user_id,
        )
        db.add(new_follow)
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(follower_count=User.follower_count + 1)
        )
        await db.commit()
        await db.refresh(target_user)
        return FollowResponse(following=True, follower_count=target_user.follower_count)


# GET /api/users/me/following — list what the current user follows


@router.get("/api/users/me/following", response_model=FollowingListResponse)
async def list_following(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowingListResponse:
    """List all artists and users the current user follows."""
    # Followed artists
    artist_result = await db.execute(
        select(Artist)
        .join(UserFollow, UserFollow.followed_artist_id == Artist.id)
        .where(UserFollow.follower_id == current_user.id)
        .order_by(Artist.name)
    )
    artists = artist_result.scalars().all()

    artist_items = [
        FollowingArtistItem(
            id=a.id,
            name=a.name,
            artwork_count=a.artwork_count,
            follower_count=a.follower_count,
        )
        for a in artists
    ]

    # Followed users
    user_result = await db.execute(
        select(User)
        .join(UserFollow, UserFollow.followed_user_id == User.id)
        .where(UserFollow.follower_id == current_user.id)
        .order_by(User.display_name)
    )
    users = user_result.scalars().all()

    user_items = [
        FollowingUserItem(
            id=u.id,
            display_name=u.display_name,
            follower_count=u.follower_count,
        )
        for u in users
    ]

    return FollowingListResponse(artists=artist_items, users=user_items)


# GET /api/artists/:id/followers — public follower count


@router.get("/api/artists/{artist_id}/followers", response_model=FollowerCountResponse)
async def get_artist_follower_count(
    artist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FollowerCountResponse:
    """Get the follower count for an artist. Public endpoint."""
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artist not found"
        )
    return FollowerCountResponse(follower_count=artist.follower_count)
