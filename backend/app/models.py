"""SQLAlchemy models for DuvarSanat."""

import uuid
from datetime import date, datetime, timezone

import sqlalchemy as sa
from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass




class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    profile_type: Mapped[str] = mapped_column(String(20), default="explorer", server_default="explorer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Moderation
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # columns
    tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_links: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_votes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    follower_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # relationships
    photos: Mapped[list["Photo"]] = relationship(back_populates="user")
    artworks: Mapped[list["Artwork"]] = relationship(back_populates="created_by_user")

    # relationships
    votes: Mapped[list["PhotoVote"]] = relationship(back_populates="user")
    badges: Mapped[list["UserBadge"]] = relationship(back_populates="user")
    conversations: Mapped[list["ConversationParticipant"]] = relationship(back_populates="user")
    sent_messages: Mapped[list["Message"]] = relationship(back_populates="sender")
    blocks_given: Mapped[list["UserBlock"]] = relationship(
        back_populates="blocker", foreign_keys="[UserBlock.blocker_id]"
    )
    blocks_received: Mapped[list["UserBlock"]] = relationship(
        back_populates="blocked", foreign_keys="[UserBlock.blocked_id]"
    )


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    artwork_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # columns
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_links: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aliases = mapped_column(ARRAY(String), nullable=True)
    follower_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), unique=True, nullable=True
    )

    # Relationships
    artworks: Mapped[list["Artwork"]] = relationship(back_populates="artist")
    claims: Mapped[list["ArtistClaim"]] = relationship(back_populates="artist")


class Artwork(Base):
    __tablename__ = "artworks"
    __table_args__ = (
        Index("ix_artworks_location", "location", postgresql_using="gist"),
        Index("ix_artworks_artist_id", "artist_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    artist_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("artists.id"), nullable=True)
    neighborhood_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("neighborhoods.id"), nullable=True
    )
    style_embedding = mapped_column(Vector(256), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    artist: Mapped[Artist | None] = relationship(back_populates="artworks")
    neighborhood: Mapped["Neighborhood | None"] = relationship(back_populates="artworks")
    created_by_user: Mapped[User] = relationship(back_populates="artworks")
    photos: Mapped[list["Photo"]] = relationship(back_populates="artwork")
    art_of_the_day_entries: Mapped[list["ArtOfTheDay"]] = relationship(back_populates="artwork")


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        Index("ix_photos_location", "location", postgresql_using="gist"),
        Index("ix_photos_artwork_date", "artwork_id", "date_taken"),
        Index("ix_photos_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    artwork_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("artworks.id"), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    date_taken: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    image_embedding = mapped_column(Vector(512), nullable=True)
    style_embedding = mapped_column(Vector(256), nullable=True)
    date_uploaded: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # columns
    categories = mapped_column(ARRAY(String), nullable=True, default=list)

    # Moderation
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    downvote_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # columns
    vote_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    vote_count_night: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    vote_count_day: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    vote_count_seasonal: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relationships
    user: Mapped[User] = relationship(back_populates="photos")
    artwork: Mapped[Artwork | None] = relationship(back_populates="photos")
    votes: Mapped[list["PhotoVote"]] = relationship(back_populates="photo")




class ArtOfTheDay(Base):
    """Daily featured artwork selection."""

    __tablename__ = "art_of_the_day"
    __table_args__ = (
        Index("ix_art_of_the_day_featured_date", "featured_date"),
        Index("ix_art_of_the_day_artwork_id", "artwork_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    artwork_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("artworks.id"), nullable=False)
    featured_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artwork: Mapped["Artwork"] = relationship(back_populates="art_of_the_day_entries")


class PhotoVote(Base):
    """User vote on a photo, optionally in a category."""

    __tablename__ = "photo_votes"
    __table_args__ = (
        UniqueConstraint("user_id", "photo_id", "category", name="uq_photo_votes_user_photo_cat"),
        Index("ix_photo_votes_photo_id", "photo_id"),
        Index("ix_photo_votes_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="overall", server_default="overall"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="votes")
    photo: Mapped["Photo"] = relationship(back_populates="votes")




class Conversation(Base):
    """A direct message thread between users."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    participants: Mapped[list["ConversationParticipant"]] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class ConversationParticipant(Base):
    """Junction table linking users to conversations."""

    __tablename__ = "conversation_participants"
    __table_args__ = (
        Index("ix_conv_participants_user_id", "user_id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship(back_populates="conversations")


class Message(Base):
    """An individual message within a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_sender_id", "sender_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship(back_populates="sent_messages")


class UserBlock(Base):
    """Block relationship between users."""

    __tablename__ = "user_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
        CheckConstraint("blocker_id != blocked_id", name="ck_user_blocks_no_self_block"),
        Index("ix_user_blocks_blocked_id", "blocked_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    blocker_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    blocker: Mapped["User"] = relationship(
        back_populates="blocks_given", foreign_keys=[blocker_id]
    )
    blocked: Mapped["User"] = relationship(
        back_populates="blocks_received", foreign_keys=[blocked_id]
    )


class LeaderboardEntry(Base):
    """Pre-computed leaderboard snapshot entry."""

    __tablename__ = "leaderboard_entries"
    __table_args__ = (
        UniqueConstraint("board_type", "period", "rank", name="uq_leaderboard_board_period_rank"),
        CheckConstraint(
            "user_id IS NOT NULL OR artist_id IS NOT NULL",
            name="ck_leaderboard_has_entity",
        ),
        Index("ix_leaderboard_board_period", "board_type", "period", "rank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("artists.id", ondelete="SET NULL"), nullable=True
    )
    board_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserBadge(Base):
    """Achievement badge awarded to a user."""

    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_type", name="uq_user_badges_user_type"),
        Index("ix_user_badges_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    badge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="badges")




class Neighborhood(Base):
    """Istanbul neighborhood reference data."""

    __tablename__ = "neighborhoods"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_tr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    artwork_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    artworks: Mapped[list["Artwork"]] = relationship(back_populates="neighborhood")


class ArtistSuggestion(Base):
    """Artist suggestion with consensus model."""

    __tablename__ = "artist_suggestions"
    __table_args__ = (
        UniqueConstraint("artwork_id", "suggested_by", name="uq_artist_suggestions_artwork_user"),
        Index("ix_artist_suggestions_artwork_status", "artwork_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    artwork_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("artworks.id", ondelete="CASCADE"), nullable=False
    )
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("artists.id", ondelete="SET NULL"), nullable=True
    )
    suggested_name: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserFavorite(Base):
    """User favorite on an artwork."""

    __tablename__ = "user_favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    artwork_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("artworks.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comment(Base):
    """Comment on an artwork or artist."""

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_target", "target_type", "target_id", "created_at"),
        Index("ix_comments_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)




class UserFollow(Base):
    """Polymorphic follow relationship: a user can follow an artist or another user."""

    __tablename__ = "user_follows"
    __table_args__ = (
        CheckConstraint(
            "(followed_artist_id IS NOT NULL AND followed_user_id IS NULL) OR "
            "(followed_artist_id IS NULL AND followed_user_id IS NOT NULL)",
            name="ck_user_follows_exactly_one",
        ),
        UniqueConstraint("follower_id", "followed_artist_id", name="uq_user_follows_artist"),
        UniqueConstraint("follower_id", "followed_user_id", name="uq_user_follows_user"),
        Index("ix_user_follows_follower", "follower_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    follower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    followed_artist_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("artists.id", ondelete="CASCADE"), nullable=True
    )
    followed_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Artist Verification Models


class ArtistClaim(Base):
    """A user's claim to be a particular artist, pending moderator review."""

    __tablename__ = "artist_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "artist_id", name="uq_artist_claims_user_artist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
    )
    verification_text: Mapped[str] = mapped_column(Text, nullable=False)
    verification_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    artist: Mapped["Artist"] = relationship(back_populates="claims")




class Challenge(Base):
    """A challenge that users can complete to earn badges."""

    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    challenge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    badge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    criteria: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    progress_entries: Mapped[list["ChallengeProgress"]] = relationship(back_populates="challenge")


class ChallengeProgress(Base):
    """Tracks a user's progress toward completing a challenge."""

    __tablename__ = "challenge_progress"
    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_progress_challenge_user"),
        Index("ix_challenge_progress_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    challenge: Mapped["Challenge"] = relationship(back_populates="progress_entries")


class WalkingTour(Base):
    """A walking tour through a neighborhood visiting artworks."""

    __tablename__ = "walking_tours"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    neighborhood_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("neighborhoods.id"), nullable=True
    )
    total_distance_m: Mapped[int] = mapped_column(Integer, default=0)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    artwork_count: Mapped[int] = mapped_column(Integer, default=0)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    neighborhood: Mapped["Neighborhood | None"] = relationship()
    stops: Mapped[list["WalkingTourStop"]] = relationship(
        back_populates="tour", order_by="WalkingTourStop.stop_order"
    )


class WalkingTourStop(Base):
    """A stop on a walking tour, linking to an artwork."""

    __tablename__ = "walking_tour_stops"
    __table_args__ = (
        Index("ix_walking_tour_stops_tour", "tour_id", "stop_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tour_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("walking_tours.id", ondelete="CASCADE"), nullable=False
    )
    artwork_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("artworks.id", ondelete="CASCADE"), nullable=False
    )
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_from_previous_m: Mapped[int] = mapped_column(Integer, default=0)

    tour: Mapped["WalkingTour"] = relationship(back_populates="stops")
    artwork: Mapped["Artwork"] = relationship()


class Notification(Base):
    """In-app notification for a user."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Content Moderation Models


class ContentFlag(Base):
    """A user-submitted flag/report on content (photo, comment, artwork, or user)."""

    __tablename__ = "content_flags"
    __table_args__ = (
        Index("ix_content_flags_target", "target_type", "target_id"),
        Index("ix_content_flags_status", "status"),
        Index("ix_content_flags_reporter", "reporter_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SiteSetting(Base):
    """Admin-configurable feature toggle stored as key-value pair."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModerationLog(Base):
    """Audit log for all moderation actions. Supports revert."""

    __tablename__ = "moderation_log"
    __table_args__ = (
        Index("ix_moderation_log_target", "target_type", "target_id"),
        Index("ix_moderation_log_moderator", "moderator_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    moderator_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    flag_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("content_flags.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reverted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
