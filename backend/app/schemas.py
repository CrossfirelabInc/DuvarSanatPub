"""Pydantic schemas for request/response validation."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator



class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    bio: str | None
    role: str
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse




class LocationResponse(BaseModel):
    latitude: float
    longitude: float


class PhotoResponse(BaseModel):
    """Response for a single photo."""

    id: uuid.UUID
    image_url: str
    location: LocationResponse
    date_taken: datetime | None = None
    date_uploaded: datetime
    artwork_id: uuid.UUID | None = None
    auto_merged_artwork_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class PhotoDetailResponse(BaseModel):
    """Photo with uploader info, used in artwork detail."""

    id: uuid.UUID
    image_url: str
    thumbnail_url: str | None = None
    date_taken: datetime | None = None
    date_uploaded: datetime
    user_id: uuid.UUID
    user_display_name: str
    vote_count: int = 0
    categories: list[str] = []




class CreateArtworkRequest(BaseModel):
    title: str | None = Field(None, max_length=300)
    description: str | None = Field(None, max_length=5000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    photo_id: uuid.UUID


class LinkPhotoRequest(BaseModel):
    photo_id: uuid.UUID


class ArtworkResponse(BaseModel):
    """Full artwork response."""

    id: uuid.UUID
    title: str | None = None
    description: str | None = None
    latitude: float
    longitude: float
    status: str
    photo_count: int
    artist_id: uuid.UUID | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ArtworkDetailResponse(BaseModel):
    """Artwork detail with related data."""

    id: uuid.UUID
    title: str | None = None
    description: str | None = None
    latitude: float
    longitude: float
    status: str
    photo_count: int
    artist_id: uuid.UUID | None = None
    artist_name: str | None = None
    created_by: uuid.UUID
    creator_display_name: str
    photos: list[PhotoDetailResponse]
    created_at: datetime
    updated_at: datetime
    suggestions: list["SuggestionItem"] = []
    is_favorited: bool = False


class ArtworkNearbyResponse(BaseModel):
    """Lightweight artwork for nearby query results."""

    id: uuid.UUID
    title: str | None = None
    status: str
    latitude: float
    longitude: float
    photo_count: int
    thumbnail_url: str | None = None


ArtworkMapItem = ArtworkNearbyResponse
"""Alias: map view items have the same shape as nearby results."""




class ArtworkSummaryResponse(BaseModel):
    """Lightweight artwork item used in artist detail."""

    id: uuid.UUID
    title: str | None = None
    status: str
    thumbnail_url: str | None = None
    photo_count: int = 0


class ArtistDetailResponse(BaseModel):
    """Full artist detail with list of attributed artworks."""

    id: uuid.UUID
    name: str
    bio: str | None = None
    aliases: list[str] | None = None
    website: str | None = None
    social_links: dict | None = None
    artwork_count: int
    total_photos: int = 0
    active_since: datetime | None = None
    artworks: list[ArtworkSummaryResponse]
    follower_count: int = 0
    is_following: bool = False
    claimed_by_user_id: str | None = None
    verified_at: datetime | None = None


class SuggestArtistRequest(BaseModel):
    """Request body for suggesting an artist for an artwork."""

    artist_name: str = Field(min_length=1, max_length=255)


class UpdateArtistRequest(BaseModel):
    """Request body for moderators to update artist profiles."""

    bio: str | None = Field(None, max_length=5000)
    website: str | None = Field(None, max_length=500)
    social_links: dict | None = None
    aliases: list[str] | None = Field(None, max_length=20)




class UserPhotoItem(BaseModel):
    """Photo item shown on a user profile."""

    id: uuid.UUID
    image_url: str
    thumbnail_url: str | None = None
    artwork_id: uuid.UUID | None = None
    date_uploaded: datetime


class UserProfileResponse(BaseModel):
    """Public user profile."""

    id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    tagline: str | None = None
    website: str | None = None
    social_links: dict | None = None
    created_at: datetime
    total_photos: int
    total_artworks: int
    artworks_discovered: int
    unique_artworks_contributed: int
    photos: list[UserPhotoItem]
    follower_count: int = 0
    is_following: bool = False


class UpdateProfileRequest(BaseModel):
    """Request body for updating the current user's profile."""

    display_name: str | None = Field(None, min_length=2, max_length=100)
    bio: str | None = Field(None, max_length=5000)
    tagline: str | None = Field(None, max_length=200)
    website: str | None = Field(None, max_length=500)
    social_links: dict | None = None
    profile_type: str | None = None

    @field_validator("social_links")
    @classmethod
    def validate_social_links(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        for key, value in v.items():
            if not isinstance(key, str) or len(key) > 50:
                raise ValueError("Social link keys must be strings under 50 characters")
            if value is not None and (not isinstance(value, str) or len(value) > 200):
                raise ValueError("Social link values must be strings under 200 characters")
        return v


class UserDiscoveryItem(BaseModel):
    """Artwork discovered (first cataloged) by a user."""

    id: uuid.UUID
    title: str | None = None
    status: str
    thumbnail_url: str | None = None
    photo_count: int
    created_at: datetime




class MatchResultItem(BaseModel):
    """A single artwork match from image similarity search."""

    artwork_id: uuid.UUID
    title: str | None = None
    thumbnail_url: str | None = None
    latitude: float
    longitude: float
    similarity: float


class MatchResponse(BaseModel):
    """Response from the /api/photos/match endpoint."""

    matches: list[MatchResultItem]




class ArtworkStatsResponse(BaseModel):
    """Platform-wide statistics for the stats bar."""

    total_artworks: int
    artworks_without_artist: int
    total_photos: int
    total_artists: int




class ArtOfTheDayResponse(BaseModel):
    """Current day's featured artwork."""

    artwork_id: uuid.UUID
    title: str | None = None
    description: str | None = None
    artist_name: str | None = None
    latitude: float
    longitude: float
    featured_date: str
    photo_url: str | None = None
    photo_count: int


class ArtOfTheDayHistoryItem(BaseModel):
    """A single entry in the Art of the Day history."""

    artwork_id: uuid.UUID
    title: str | None = None
    artist_name: str | None = None
    thumbnail_url: str | None = None
    featured_date: str




class SuggestionItem(BaseModel):
    """A single artist suggestion with its vote count."""

    artist_name: str
    count: int
    status: str


class ArtworkDetailWithSuggestionsResponse(ArtworkDetailResponse):
    """Artwork detail extended with artist suggestions."""

    suggestions: list[SuggestionItem] = []


class ArtistSuggestionResponse(BaseModel):
    """Response after creating an artist suggestion."""

    artwork_id: uuid.UUID
    suggestion_id: uuid.UUID
    artist_name: str
    status: str
    consensus_reached: bool = False
    suggestions: list[SuggestionItem] = []




class NeighborhoodResponse(BaseModel):
    """Neighborhood summary for listings."""

    id: uuid.UUID
    name: str
    slug: str
    artwork_count: int

    model_config = {"from_attributes": True}


class NeighborhoodDetailResponse(BaseModel):
    """Neighborhood detail with its artworks."""

    id: uuid.UUID
    name: str
    name_tr: str | None = None
    slug: str
    description: str | None = None
    artwork_count: int
    artworks: list[ArtworkNearbyResponse]

    model_config = {"from_attributes": True}




class WallChangedItem(BaseModel):
    """An artwork that has new photos recently (before/after)."""

    artwork_id: uuid.UUID
    title: str | None = None
    artist_name: str | None = None
    neighborhood: str | None = None
    oldest_photo_url: str | None = None
    newest_photo_url: str | None = None
    photo_count: int


class RecentDiscoveryItem(BaseModel):
    """A recently discovered artwork."""

    id: uuid.UUID
    title: str | None = None
    artist_name: str | None = None
    thumbnail_url: str | None = None
    neighborhood: str | None = None
    created_at: datetime


class HomepageStatsResponse(BaseModel):
    """Platform-wide stats for the homepage."""

    total_artworks: int
    total_photos: int
    total_artists: int
    walls_changed_this_week: int


class TopContributorItem(BaseModel):
    """A top contributor by photo count."""

    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None = None
    photo_count: int
    artwork_count: int


class TopArtworkItem(BaseModel):
    """An artwork ranked by total vote count, for the homepage sidebar."""

    id: uuid.UUID
    title: str | None = None
    thumbnail_url: str | None = None
    total_votes: int


class HomepageResponse(BaseModel):
    """Full homepage data in a single response."""

    art_of_the_day: ArtOfTheDayResponse | None = None
    stats: HomepageStatsResponse
    walls_changed: list[WallChangedItem]
    recent_discoveries: list[RecentDiscoveryItem]
    neighborhoods: list[NeighborhoodResponse]
    mysteries_count: int
    top_contributors: list[TopContributorItem] = []
    top_artworks: list[TopArtworkItem] = []





class CreateCommentRequest(BaseModel):
    target_type: str = Field(..., pattern="^(artwork|artist)$")
    target_id: uuid.UUID
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def strip_html_tags(cls, v: str) -> str:
        """Strip HTML tags from comment content to prevent stored XSS."""
        return re.sub(r"<[^>]+>", "", v).strip()


class CommentResponse(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    user_id: uuid.UUID
    user_display_name: str
    content: str
    created_at: datetime




class VoteResponse(BaseModel):
    voted: bool
    vote_count: int


class SuggestTitleResponse(BaseModel):
    suggested_title: str | None = None




class SimilarArtworkItem(BaseModel):
    artwork_id: uuid.UUID
    title: str | None = None
    thumbnail_url: str | None = None
    similarity: float


class StyleSimilarArtworkItem(BaseModel):
    """An artwork with similar artistic style."""

    artwork_id: uuid.UUID
    title: str | None = None
    thumbnail_url: str | None = None
    similarity: float


class StyleSimilarArtistItem(BaseModel):
    """An artist with similar artistic style."""

    artist_id: uuid.UUID
    name: str
    artwork_count: int
    similarity: float




class FavoriteResponse(BaseModel):
    favorited: bool


class FavoriteItem(BaseModel):
    artwork_id: uuid.UUID
    title: str | None = None
    thumbnail_url: str | None = None
    status: str
    created_at: datetime




class SearchArtworkItem(BaseModel):
    id: uuid.UUID
    title: str | None = None
    thumbnail_url: str | None = None
    status: str
    artist_name: str | None = None


class SearchArtistItem(BaseModel):
    id: uuid.UUID
    name: str
    artwork_count: int


class SearchResponse(BaseModel):
    artworks: list[SearchArtworkItem]
    artists: list[SearchArtistItem]



class HealthResponse(BaseModel):
    status: str = "ok"




class FollowResponse(BaseModel):
    """Response after toggling a follow."""

    following: bool
    follower_count: int


class FollowingArtistItem(BaseModel):
    """Artist item in the following list."""

    id: uuid.UUID
    name: str
    artwork_count: int
    follower_count: int


class FollowingUserItem(BaseModel):
    """User item in the following list."""

    id: uuid.UUID
    display_name: str
    follower_count: int


class FollowingListResponse(BaseModel):
    """List of entities the current user follows."""

    artists: list[FollowingArtistItem]
    users: list[FollowingUserItem]


class FollowerCountResponse(BaseModel):
    """Public follower count for an entity."""

    follower_count: int




class ChallengeResponse(BaseModel):
    """A challenge with optional user progress."""

    id: uuid.UUID
    title: str
    description: str
    challenge_type: str
    badge_type: str
    progress: int = 0
    target: int = 0
    completed: bool = False


class ChallengeProgressResponse(BaseModel):
    """Updated progress after a challenge check."""

    challenge_id: uuid.UUID
    progress: int
    target: int
    completed: bool
    badge_awarded: bool = False




class TourListItem(BaseModel):
    """Summary of a walking tour for list views."""

    id: uuid.UUID
    title: str
    neighborhood_name: str | None = None
    artwork_count: int
    total_distance_m: int
    estimated_minutes: int


class TourStopItem(BaseModel):
    """A single stop on a walking tour."""

    stop_order: int
    artwork_id: uuid.UUID
    artwork_title: str | None = None
    thumbnail_url: str | None = None
    latitude: float
    longitude: float
    distance_from_previous_m: int


class TourDetailResponse(BaseModel):
    """Full tour detail with ordered stops."""

    id: uuid.UUID
    title: str
    description: str | None = None
    stops: list[TourStopItem]




class NotificationResponse(BaseModel):
    """A user notification."""

    id: uuid.UUID
    type: str
    title: str
    message: str | None = None
    link: str | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    """Count of unread notifications."""

    count: int




class CreateClaimRequest(BaseModel):
    """Request body for claiming an artist profile."""

    verification_text: str = Field(min_length=10, max_length=2000)
    verification_url: str | None = Field(None, max_length=500)


class ClaimResponse(BaseModel):
    """Response for an artist claim."""

    id: uuid.UUID
    user_id: uuid.UUID
    artist_id: uuid.UUID
    verification_text: str
    verification_url: str | None = None
    status: str
    reviewed_by: uuid.UUID | None = None
    review_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    artist_name: str | None = None
    claimant_display_name: str | None = None


class RejectClaimRequest(BaseModel):
    """Request body for rejecting a claim."""

    note: str | None = None


class PromoteRequest(BaseModel):
    """Request body for promoting a user's role."""

    user_id: uuid.UUID
    role: str = Field(pattern="^(moderator|admin)$")




class LeaderboardEntry(BaseModel):
    """A single entry on the leaderboard."""

    rank: int
    id: uuid.UUID
    name: str
    score: int
    follower_count: int
    metric: str
    avatar_url: str | None = None


class LeaderboardResponse(BaseModel):
    """Full leaderboard response."""

    type: str
    period: str
    entries: list[LeaderboardEntry]




class CreateFlagRequest(BaseModel):
    """Request to flag/report content."""

    target_type: str = Field(..., pattern="^(photo|comment|artwork|user)$")
    target_id: uuid.UUID
    reason: str = Field(..., pattern="^(inappropriate|spam|harassment|other)$")
    description: str | None = Field(None, max_length=1000)


class FlagResponse(BaseModel):
    """Response for a content flag."""

    id: uuid.UUID
    reporter_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    reason: str
    description: str | None = None
    status: str
    reviewed_by: uuid.UUID | None = None
    review_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    reporter_display_name: str | None = None

    model_config = {"from_attributes": True}


class ReviewFlagRequest(BaseModel):
    """Request to review a flag (delete content or dismiss)."""

    action: str = Field(..., pattern="^(delete|dismissed)$")
    note: str | None = Field(None, max_length=1000)


class BanUserRequest(BaseModel):
    """Request to ban a user."""

    user_id: uuid.UUID
