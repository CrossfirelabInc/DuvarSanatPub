"""Integration-style tests for API endpoints using mocked DB dependencies.

Each test overrides get_db and (when needed) get_current_user so that
no real PostgreSQL / PostGIS connection is required.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import Artist, Artwork, Photo, User
from tests.conftest import make_mock_db, make_user


# Helpers


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalar_one(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _scalars_all(values):
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    result.scalars.return_value = scalars
    return result


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _make_photo(
    user_id: uuid.UUID,
    photo_id: uuid.UUID | None = None,
    artwork_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock Photo model instance."""
    photo = MagicMock(spec=Photo)
    photo.id = photo_id or uuid.uuid4()
    photo.user_id = user_id
    photo.artwork_id = artwork_id
    photo.image_url = "/uploads/test.jpg"
    photo.location = None
    photo.date_taken = None
    photo.date_uploaded = datetime(2025, 6, 1, tzinfo=timezone.utc)
    photo.image_embedding = None
    photo.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    photo.thumbnail_url = None
    photo.vote_count = 0
    photo.vote_count_night = 0
    photo.vote_count_day = 0
    photo.vote_count_seasonal = 0
    return photo


def _make_artwork(
    created_by: uuid.UUID,
    artwork_id: uuid.UUID | None = None,
    artist_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock Artwork model instance."""
    aw = MagicMock(spec=Artwork)
    aw.id = artwork_id or uuid.uuid4()
    aw.title = "Test Mural"
    aw.description = "A test artwork"
    aw.location = None
    aw.artist_id = artist_id
    aw.status = "active"
    aw.created_by = created_by
    aw.photo_count = 1
    aw.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    aw.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return aw


def _make_artist(artist_id: uuid.UUID | None = None, name: str = "Banksy") -> MagicMock:
    """Create a mock Artist model instance."""
    artist = MagicMock(spec=Artist)
    artist.id = artist_id or uuid.uuid4()
    artist.name = name
    artist.bio = None
    artist.artwork_count = 3
    artist.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.website = None
    artist.social_links = None
    artist.verified_at = None
    artist.aliases = None
    artist.follower_count = 0
    return artist


def _setup_overrides(db, user=None):
    """Override get_db and optionally get_current_user on the FastAPI app."""
    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override

    if user is not None:
        async def _auth_override():
            return user
        app.dependency_overrides[get_current_user] = _auth_override


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


# GET /api/artworks/stats


class TestArtworkStats:

    @pytest.mark.asyncio
    async def test_stats_returns_counts(self):
        db = make_mock_db()
        # scalar() is called 4 times for the 4 counts
        db.scalar = AsyncMock(side_effect=[10, 3, 50, 5])
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/artworks/stats")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_artworks"] == 10
        assert body["artworks_without_artist"] == 3
        assert body["total_photos"] == 50
        assert body["total_artists"] == 5

    @pytest.mark.asyncio
    async def test_stats_all_zero(self):
        db = make_mock_db()
        db.scalar = AsyncMock(return_value=0)
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/artworks/stats")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_artworks"] == 0


# GET /api/users/{user_id}/profile


class TestUserProfile:

    @pytest.mark.asyncio
    async def test_profile_not_found(self):
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/users/{uuid.uuid4()}/profile")
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_profile_found(self):
        user = make_user(display_name="ProfileUser", bio="Hello")
        db = make_mock_db()

        # execute calls: 1) user lookup, 2) photo count, 3) artwork count,
        # 4) unique artworks contributed, 5) photos list
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(user),  # user lookup
            _scalar_one(5),             # photo count
            _scalar_one(2),             # artwork count
            _scalar_one(1),             # unique artworks contributed
            _scalars_all([]),           # recent photos
        ])
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/users/{user.id}/profile")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "ProfileUser"
        assert body["total_photos"] == 5
        assert body["total_artworks"] == 2


# PATCH /api/users/me


class TestUpdateProfile:

    @pytest.mark.asyncio
    async def test_update_display_name(self):
        user = make_user(display_name="OldName")
        db = make_mock_db()
        # Uniqueness check: no duplicate found
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))

        async def fake_refresh(obj):
            obj.display_name = "NewName"

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    "/api/users/me",
                    json={"display_name": "NewName"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["display_name"] == "NewName"

    @pytest.mark.asyncio
    async def test_update_requires_auth(self):
        """PATCH /api/users/me without auth returns 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.patch("/api/users/me", json={"bio": "new bio"})

        assert resp.status_code in (401, 403)


# GET /api/artists/{artist_id}


class TestArtistDetail:

    @pytest.mark.asyncio
    async def test_artist_not_found(self):
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/artists/{uuid.uuid4()}")
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_artist_found(self):
        artist = _make_artist(name="Banksy")
        db = make_mock_db()

        # First execute: artist lookup. Second: artworks query.
        # Third: active_since (min created_at).
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artist),
            _all([]),  # no artworks
            _scalar_one(None),  # active_since
        ])
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/artists/{artist.id}")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Banksy"
        assert body["artworks"] == []


# POST /api/photos/upload (auth required)


class TestPhotoUpload:

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self):
        """Upload without auth header returns 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/photos/upload",
                data={"latitude": "41.0", "longitude": "29.0"},
                files={"file": ("test.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
            )

        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_upload_invalid_content_type(self):
        """Non-image content type is rejected with 400."""
        user = make_user()
        db = make_mock_db()
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/photos/upload",
                    data={"latitude": "41.0", "longitude": "29.0"},
                    files={"file": ("test.txt", b"not an image", "text/plain")},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 400
        assert "Unsupported image format" in resp.json()["detail"] or "JPEG" in resp.json()["detail"]


# POST /api/photos/match (auth required)


class TestPhotoMatch:

    @pytest.mark.asyncio
    async def test_match_requires_auth(self):
        """Match without auth returns 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/photos/match",
                files={"file": ("test.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
            )

        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_match_returns_empty_when_clip_not_loaded(self):
        """When CLIP is not loaded, match returns empty matches array."""
        user = make_user()
        db = make_mock_db()
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            # Ensure clip_service reports not loaded
            with patch("app.routers.photos.clip_service") as mock_clip:
                mock_clip.is_loaded = False
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    resp = await client.post(
                        "/api/photos/match",
                        files={"file": ("test.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
                        headers={"Authorization": f"Bearer {token}"},
                    )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["matches"] == []


# POST /api/artworks (auth required)


class TestCreateArtwork:

    @pytest.mark.asyncio
    async def test_create_requires_auth(self):
        """POST /api/artworks without auth returns 403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/artworks", json={
                "latitude": 41.0, "longitude": 29.0,
                "photo_id": str(uuid.uuid4()),
            })

        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_photo_not_found(self):
        """If photo_id doesn't exist, returns 404."""
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/artworks",
                    json={
                        "latitude": 41.0, "longitude": 29.0,
                        "photo_id": str(uuid.uuid4()),
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 404
        assert "Photo not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_photo_not_owned(self):
        """If photo belongs to a different user, returns 403."""
        user = make_user()
        other_user_id = uuid.uuid4()
        photo = _make_photo(user_id=other_user_id)
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(photo))
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/artworks",
                    json={
                        "latitude": 41.0, "longitude": 29.0,
                        "photo_id": str(photo.id),
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code in (401, 403)
        assert "your own photos" in resp.json()["detail"]


# PATCH /api/artworks/{id}/link-photo (auth required)


class TestLinkPhoto:

    @pytest.mark.asyncio
    async def test_link_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.patch(
                f"/api/artworks/{uuid.uuid4()}/link-photo",
                json={"photo_id": str(uuid.uuid4())},
            )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_link_artwork_not_found(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    f"/api/artworks/{uuid.uuid4()}/link-photo",
                    json={"photo_id": str(uuid.uuid4())},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 404


# POST /api/artworks/{id}/suggest-artist (auth required)


class TestSuggestArtist:

    @pytest.mark.asyncio
    async def test_suggest_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                f"/api/artworks/{uuid.uuid4()}/suggest-artist",
                json={"artist_name": "Banksy"},
            )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_suggest_artwork_not_found(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artworks/{uuid.uuid4()}/suggest-artist",
                    json={"artist_name": "Banksy"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 404


# GET /api/artworks?bounds=... (bounds validation)


class TestMapDataBoundsValidation:
    """Tests for bounds parameter validation on the map data endpoint."""

    async def _get_with_bounds(self, bounds: str):
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_all([]))
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/artworks?bounds={bounds}")
        finally:
            _clear_overrides()
        return resp

    @pytest.mark.asyncio
    async def test_bounds_south_greater_than_north_returns_400(self):
        """south > north should be rejected with 400."""
        resp = await self._get_with_bounds("50.0,10.0,40.0,20.0")
        assert resp.status_code == 400
        assert "south" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bounds_latitude_out_of_range_returns_400(self):
        """south latitude outside [-90, 90] should be rejected with 400."""
        resp = await self._get_with_bounds("-100.0,10.0,40.0,20.0")
        assert resp.status_code == 400
        assert "latitude" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bounds_north_latitude_out_of_range_returns_400(self):
        """north > 90 should be rejected with 400."""
        resp = await self._get_with_bounds("40.0,10.0,100.0,20.0")
        assert resp.status_code == 400
        assert "latitude" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bounds_longitude_out_of_range_returns_400(self):
        """west longitude outside [-180, 180] should be rejected with 400."""
        resp = await self._get_with_bounds("40.0,-200.0,50.0,20.0")
        assert resp.status_code == 400
        assert "longitude" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bounds_east_longitude_out_of_range_returns_400(self):
        """east > 180 should be rejected with 400."""
        resp = await self._get_with_bounds("40.0,10.0,50.0,200.0")
        assert resp.status_code == 400
        assert "longitude" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bounds_valid_equal_south_north_returns_200(self):
        """south == north (degenerate box) is valid and should return 200."""
        resp = await self._get_with_bounds("41.0,28.0,41.0,30.0")
        assert resp.status_code == 200
