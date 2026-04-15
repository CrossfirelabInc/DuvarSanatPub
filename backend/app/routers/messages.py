"""Direct messaging endpoints: conversations, messages, and user blocking."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth import get_current_user
from app.database import get_db
from app.models import Conversation, ConversationParticipant, Message, User, UserBlock
from app.notification_utils import create_notification
from app.rate_limit import limiter

router = APIRouter(prefix="/api/messages", tags=["messages"])


# Conversations


@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all conversations for the current user, with last message preview."""
    # Get conversation IDs the user participates in
    conv_ids_q = select(ConversationParticipant.conversation_id).where(
        ConversationParticipant.user_id == current_user.id
    )

    # Latest message subquery
    latest_msg_subq = (
        select(
            Message.conversation_id,
            Message.content,
            Message.created_at,
            Message.sender_id,
            func.row_number()
            .over(partition_by=Message.conversation_id, order_by=desc(Message.created_at))
            .label("rn"),
        )
        .subquery()
    )
    latest_msg = (
        select(
            latest_msg_subq.c.conversation_id,
            latest_msg_subq.c.content,
            latest_msg_subq.c.created_at,
            latest_msg_subq.c.sender_id,
        )
        .where(latest_msg_subq.c.rn == 1)
        .subquery()
    )

    # Unread count subquery
    unread_subq = (
        select(
            Message.conversation_id,
            func.count().label("unread_count"),
        )
        .where(
            Message.sender_id != current_user.id,
            Message.read_at.is_(None),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    # Get conversations with last message
    query = (
        select(
            Conversation.id,
            Conversation.updated_at,
            latest_msg.c.content.label("last_message"),
            latest_msg.c.created_at.label("last_message_at"),
            func.coalesce(unread_subq.c.unread_count, 0).label("unread_count"),
        )
        .where(Conversation.id.in_(conv_ids_q))
        .outerjoin(latest_msg, latest_msg.c.conversation_id == Conversation.id)
        .outerjoin(unread_subq, unread_subq.c.conversation_id == Conversation.id)
        .order_by(desc(Conversation.updated_at))
        .limit(50)
    )

    result = await db.execute(query)
    conversations = result.all()

    # Get the other participant for each conversation
    conv_list = []
    for conv in conversations:
        # Find the other participant
        other_q = (
            select(User.id, User.display_name, User.avatar_url)
            .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
            .where(
                ConversationParticipant.conversation_id == conv.id,
                ConversationParticipant.user_id != current_user.id,
            )
        )
        other_result = await db.execute(other_q)
        other = other_result.first()

        conv_list.append({
            "id": str(conv.id),
            "other_user": {
                "id": str(other.id) if other else None,
                "display_name": other.display_name if other else "Unknown",
                "avatar_url": other.avatar_url if other else None,
            } if other else None,
            "last_message": conv.last_message,
            "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
            "unread_count": conv.unread_count,
        })

    return conv_list


@router.post("/conversations")
@limiter.limit("10/minute")
async def create_or_get_conversation(
    request: Request,
    other_user_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new conversation with another user, or return existing one."""
    if other_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    # Check other user exists
    other = await db.execute(select(User).where(User.id == other_user_id))
    if other.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check blocks
    block = await db.execute(
        select(UserBlock).where(
            or_(
                and_(UserBlock.blocker_id == current_user.id, UserBlock.blocked_id == other_user_id),
                and_(UserBlock.blocker_id == other_user_id, UserBlock.blocked_id == current_user.id),
            )
        )
    )
    if block.scalar_one_or_none() is not None:
        raise HTTPException(status_code=403, detail="Cannot message this user")

    # Check if conversation already exists between these two users
    my_convs = select(ConversationParticipant.conversation_id).where(
        ConversationParticipant.user_id == current_user.id
    )
    their_convs = select(ConversationParticipant.conversation_id).where(
        ConversationParticipant.user_id == other_user_id
    )
    existing = await db.execute(
        select(Conversation.id).where(
            Conversation.id.in_(my_convs),
            Conversation.id.in_(their_convs),
        )
    )
    existing_conv = existing.scalar_one_or_none()
    if existing_conv:
        return {"conversation_id": str(existing_conv)}

    # Create new conversation
    conv = Conversation()
    db.add(conv)
    await db.flush()

    db.add(ConversationParticipant(conversation_id=conv.id, user_id=current_user.id))
    db.add(ConversationParticipant(conversation_id=conv.id, user_id=other_user_id))
    await db.commit()

    return {"conversation_id": str(conv.id)}


# Messages


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get messages in a conversation. Marks received messages as read."""
    # Verify user is a participant
    participant = await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == current_user.id,
        )
    )
    if participant.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    # Get messages
    result = await db.execute(
        select(Message, User.display_name)
        .join(User, User.id == Message.sender_id)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    rows = result.all()

    # Mark unread messages from other users as read
    from datetime import datetime, timezone
    from sqlalchemy import update

    await db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()

    return [
        {
            "id": str(msg.id),
            "sender_id": str(msg.sender_id),
            "sender_name": display_name,
            "content": msg.content,
            "read_at": msg.read_at.isoformat() if msg.read_at else None,
            "created_at": msg.created_at.isoformat(),
            "is_mine": msg.sender_id == current_user.id,
        }
        for msg, display_name in reversed(rows)
    ]


@router.post("/conversations/{conversation_id}/messages")
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a message in a conversation."""
    body = await request.json()
    content = body.get("content", "").strip()
    if not content or len(content) > 5000:
        raise HTTPException(status_code=400, detail="Message must be 1-5000 characters")

    # Verify user is a participant
    participant = await db.execute(
        select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == current_user.id,
        )
    )
    if participant.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    # Check blocks
    other_participant = await db.execute(
        select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id != current_user.id,
        )
    )
    other_id = other_participant.scalar_one_or_none()
    if other_id:
        block = await db.execute(
            select(UserBlock).where(
                or_(
                    and_(UserBlock.blocker_id == current_user.id, UserBlock.blocked_id == other_id),
                    and_(UserBlock.blocker_id == other_id, UserBlock.blocked_id == current_user.id),
                )
            )
        )
        if block.scalar_one_or_none() is not None:
            raise HTTPException(status_code=403, detail="Cannot message this user")

    # Strip HTML tags
    import re
    content = re.sub(r"<[^>]+>", "", content).strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    msg = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=content,
    )
    db.add(msg)

    # Update conversation timestamp
    from sqlalchemy import update
    from datetime import datetime, timezone

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=datetime.now(timezone.utc))
    )

    # Notify the other user
    if other_id:
        preview = content[:50] + ("..." if len(content) > 50 else "")
        await create_notification(
            db,
            user_id=other_id,
            type="new_message",
            title=f"New message from {current_user.display_name}",
            message=preview,
            link="/messages",
        )

    await db.commit()
    await db.refresh(msg)

    return {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "sender_name": current_user.display_name,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
        "is_mine": True,
    }


# User Blocking


@router.post("/block/{user_id}")
async def block_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Block a user. Prevents DMs between both parties."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    # Check if already blocked
    existing = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="User already blocked")

    block = UserBlock(blocker_id=current_user.id, blocked_id=user_id)
    db.add(block)
    await db.commit()

    return {"status": "blocked"}


@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Unblock a user."""
    result = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == user_id,
        )
    )
    block = result.scalar_one_or_none()
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")

    await db.delete(block)
    await db.commit()

    return {"status": "unblocked"}
