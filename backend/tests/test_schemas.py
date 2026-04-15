"""Tests for Pydantic schema validation.

Validates field constraints, default values, and serialization behavior
for the request/response schemas used across all endpoints.
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (
    ArtistDetailResponse,
    ArtworkMapItem,
    ArtworkNearbyResponse,
    ArtworkResponse,
    ArtworkStatsResponse,
    AuthResponse,
    CreateArtworkRequest,
    HealthResponse,
    LinkPhotoRequest,
    LoginRequest,
    MatchResponse,
    MatchResultItem,
    RegisterRequest,
    SuggestArtistRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)


# RegisterRequest


class TestRegisterRequest:

    def test_valid(self):
        req = RegisterRequest(email="a@b.com", password="12345678", display_name="Ab")
        assert req.email == "a@b.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="bad", password="12345678", display_name="Ab")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="1234567", display_name="Ab")

    def test_password_exactly_8(self):
        req = RegisterRequest(email="a@b.com", password="12345678", display_name="Ab")
        assert len(req.password) == 8

    def test_display_name_too_short(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="12345678", display_name="A")

    def test_display_name_too_long(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="12345678", display_name="A" * 101)

    def test_display_name_max_length(self):
        req = RegisterRequest(email="a@b.com", password="12345678", display_name="A" * 100)
        assert len(req.display_name) == 100

    def test_missing_email(self):
        with pytest.raises(ValidationError):
            RegisterRequest(password="12345678", display_name="Ab")

    def test_missing_password(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", display_name="Ab")

    def test_missing_display_name(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="12345678")


# LoginRequest


class TestLoginRequest:

    def test_valid(self):
        req = LoginRequest(email="a@b.com", password="any")
        assert req.password == "any"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="not-email", password="x")

    def test_missing_password(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com")


# CreateArtworkRequest


class TestCreateArtworkRequest:

    def test_valid_minimal(self):
        req = CreateArtworkRequest(
            latitude=41.0, longitude=29.0, photo_id=uuid.uuid4()
        )
        assert req.title is None
        assert req.description is None

    def test_valid_full(self):
        req = CreateArtworkRequest(
            title="Mural", description="A nice mural",
            latitude=41.0, longitude=29.0, photo_id=uuid.uuid4()
        )
        assert req.title == "Mural"

    def test_latitude_out_of_range(self):
        with pytest.raises(ValidationError):
            CreateArtworkRequest(latitude=91.0, longitude=0.0, photo_id=uuid.uuid4())

    def test_latitude_negative_out_of_range(self):
        with pytest.raises(ValidationError):
            CreateArtworkRequest(latitude=-91.0, longitude=0.0, photo_id=uuid.uuid4())

    def test_longitude_out_of_range(self):
        with pytest.raises(ValidationError):
            CreateArtworkRequest(latitude=0.0, longitude=181.0, photo_id=uuid.uuid4())

    def test_longitude_negative_out_of_range(self):
        with pytest.raises(ValidationError):
            CreateArtworkRequest(latitude=0.0, longitude=-181.0, photo_id=uuid.uuid4())

    def test_boundary_values(self):
        req = CreateArtworkRequest(
            latitude=90.0, longitude=-180.0, photo_id=uuid.uuid4()
        )
        assert req.latitude == 90.0
        assert req.longitude == -180.0

    def test_missing_photo_id(self):
        with pytest.raises(ValidationError):
            CreateArtworkRequest(latitude=0.0, longitude=0.0)


# SuggestArtistRequest


class TestSuggestArtistRequest:

    def test_valid(self):
        req = SuggestArtistRequest(artist_name="Banksy")
        assert req.artist_name == "Banksy"

    def test_empty_name(self):
        with pytest.raises(ValidationError):
            SuggestArtistRequest(artist_name="")

    def test_name_too_long(self):
        with pytest.raises(ValidationError):
            SuggestArtistRequest(artist_name="A" * 256)

    def test_name_max_length(self):
        req = SuggestArtistRequest(artist_name="A" * 255)
        assert len(req.artist_name) == 255


# UpdateProfileRequest


class TestUpdateProfileRequest:

    def test_empty_body(self):
        """Both fields are optional -- empty body is valid."""
        req = UpdateProfileRequest()
        assert req.display_name is None
        assert req.bio is None

    def test_display_name_only(self):
        req = UpdateProfileRequest(display_name="NewName")
        assert req.display_name == "NewName"

    def test_bio_only(self):
        req = UpdateProfileRequest(bio="Hello world")
        assert req.bio == "Hello world"

    def test_display_name_too_short(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(display_name="A")

    def test_display_name_too_long(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(display_name="A" * 101)


# LinkPhotoRequest


class TestLinkPhotoRequest:

    def test_valid(self):
        pid = uuid.uuid4()
        req = LinkPhotoRequest(photo_id=pid)
        assert req.photo_id == pid

    def test_invalid_uuid(self):
        with pytest.raises(ValidationError):
            LinkPhotoRequest(photo_id="not-a-uuid")


# Response schemas (serialization)


class TestUserResponse:

    def test_from_dict(self):
        uid = uuid.uuid4()
        resp = UserResponse(
            id=uid, email="a@b.com", display_name="Test",
            bio=None, role="user",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        assert resp.id == uid
        assert resp.role == "user"


class TestHealthResponse:

    def test_default_status(self):
        resp = HealthResponse()
        assert resp.status == "ok"

    def test_custom_status(self):
        resp = HealthResponse(status="degraded")
        assert resp.status == "degraded"


class TestArtworkStatsResponse:

    def test_all_zeros(self):
        resp = ArtworkStatsResponse(
            total_artworks=0, artworks_without_artist=0,
            total_photos=0, total_artists=0,
        )
        assert resp.total_artworks == 0

    def test_positive_counts(self):
        resp = ArtworkStatsResponse(
            total_artworks=42, artworks_without_artist=10,
            total_photos=200, total_artists=5,
        )
        assert resp.total_artworks == 42


class TestMatchResultItem:

    def test_valid(self):
        item = MatchResultItem(
            artwork_id=uuid.uuid4(), title="Mural",
            thumbnail_url="/img.jpg",
            latitude=41.0, longitude=29.0, similarity=0.85,
        )
        assert item.similarity == 0.85

    def test_nullable_title(self):
        item = MatchResultItem(
            artwork_id=uuid.uuid4(), title=None,
            thumbnail_url=None,
            latitude=0.0, longitude=0.0, similarity=0.75,
        )
        assert item.title is None


class TestMatchResponse:

    def test_empty_matches(self):
        resp = MatchResponse(matches=[])
        assert resp.matches == []
