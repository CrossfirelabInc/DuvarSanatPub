"""Comment CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth import get_current_user
from app.database import get_db
from app.models import Artist, Artwork, Comment, User
from app.rate_limit import limiter
from app.schemas import CommentResponse, CreateCommentRequest

router = APIRouter(prefix="/api/comments", tags=["comments"])

TARGET_TYPE_MODEL = {
    "artwork": Artwork,
    "artist": Artist,
}


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_comment(
    request: Request,
    body: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """Create a comment on an artwork or artist.

    Validates target_type is 'artwork' or 'artist' and that the target exists.
    Returns the created comment with user display_name.
    """
    # Validate target exists
    model = TARGET_TYPE_MODEL.get(body.target_type)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_type must be 'artwork' or 'artist'",
        )

    result = await db.execute(select(model).where(model.id == body.target_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{body.target_type.capitalize()} not found",
        )

    comment = Comment(
        target_type=body.target_type,
        target_id=body.target_id,
        user_id=current_user.id,
        content=body.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentResponse(
        id=comment.id,
        target_type=comment.target_type,
        target_id=comment.target_id,
        user_id=comment.user_id,
        user_display_name=current_user.display_name,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("", response_model=list[CommentResponse])
async def list_comments(
    target_type: str = Query(..., pattern="^(artwork|artist)$"),
    target_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[CommentResponse]:
    """List comments for a target, ordered by created_at ascending.

    Public endpoint. Excludes soft-deleted comments.
    """
    result = await db.execute(
        select(Comment, User.display_name)
        .join(User, User.id == Comment.user_id)
        .where(
            Comment.target_type == target_type,
            Comment.target_id == target_id,
            Comment.is_deleted == False,  # noqa: E712
        )
        .order_by(Comment.created_at.asc())
    )
    rows = result.all()

    return [
        CommentResponse(
            id=comment.id,
            target_type=comment.target_type,
            target_id=comment.target_id,
            user_id=comment.user_id,
            user_display_name=display_name,
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment, display_name in rows
    ]


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a comment.

    Only the comment author or a moderator/admin can delete.
    Sets is_deleted = True.
    """
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    if comment.user_id != current_user.id and current_user.role not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        )

    comment.is_deleted = True
    await db.commit()
