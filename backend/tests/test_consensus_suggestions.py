"""Tests for the redesigned artist suggestion consensus system."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import Artist, ArtistSuggestion, Artwork
from tests.conftest import make_mock_db, make_user


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _make_artwork(
    created_by: uuid.UUID,
    artwork_id: uuid.UUID | None = None,
    artist_id: uuid.UUID | None = None,
) -> MagicMock:
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
    aw.neighborhood_id = None
    return aw


def _make_artist(artist_id: uuid.UUID | None = None, name: str = "Banksy") -> MagicMock:
    artist = MagicMock(spec=Artist)
    artist.id = artist_id or uuid.uuid4()
    artist.name = name
    artist.bio = None
    artist.artwork_count = 0
    artist.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.website = None
    artist.social_links = None
    artist.verified_at = None
    artist.aliases = None
    artist.follower_count = 0
    return artist


def _make_suggestion(
    artwork_id: uuid.UUID,
    artist_id: uuid.UUID,
    user_id: uuid.UUID,
    suggested_name: str = "Banksy",
    status: str = "pending",
) -> MagicMock:
    s = MagicMock(spec=ArtistSuggestion)
    s.id = uuid.uuid4()
    s.artwork_id = artwork_id
    s.artist_id = artist_id
    s.suggested_name = suggested_name
    s.suggested_by = user_id
    s.status = status
    s.resolved_by = None
    s.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    s.resolved_at = None
    return s


def _setup_overrides(db, user=None):
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


class TestSuggestArtistConsensus:

    @pytest.mark.asyncio
    async def test_suggest_requires_auth(self):
        """POST /api/artworks/{id}/suggest-artist without auth returns 401/403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                f"/api/artworks/{uuid.uuid4()}/suggest-artist",
                json={"artist_name": "Banksy"},
            )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_suggest_artwork_not_found(self):
        """Returns 404 if artwork does not exist."""
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

    @pytest.mark.asyncio
    async def test_suggest_duplicate_returns_409(self):
        """Returns 409 if user already suggested for this artwork."""
        user = make_user()
        artwork = _make_artwork(created_by=user.id)
        existing_suggestion = _make_suggestion(
            artwork_id=artwork.id,
            artist_id=uuid.uuid4(),
            user_id=user.id,
        )
        db = make_mock_db()

        # 1) artwork lookup, 2) existing suggestion check
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artwork),       # artwork found
            _scalar_one_or_none(existing_suggestion),  # already suggested
        ])
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artworks/{artwork.id}/suggest-artist",
                    json={"artist_name": "Banksy"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 409
        assert "already suggested" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_suggest_creates_new_artist_if_not_found(self):
        """Creates a new artist if name doesn't match existing artists."""
        user = make_user()
        artwork = _make_artwork(created_by=user.id)
        db = make_mock_db()

        artist_id = uuid.uuid4()

        # Use SimpleNamespace for rows so Pydantic can read real values
        from types import SimpleNamespace

        consensus_row = SimpleNamespace(artist_id=artist_id, cnt=1)
        summary_row = SimpleNamespace(suggested_name="NewArtist", cnt=1, status="pending")

        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artwork),       # artwork found
            _scalar_one_or_none(None),          # no existing suggestion by user
            _scalar_one_or_none(None),          # no existing artist by name
            _all([consensus_row]),               # consensus count
            _all([summary_row]),                 # suggestion summary
        ])

        async def fake_refresh(obj):
            # Ensure the suggestion object gets an id after "refresh"
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = uuid.uuid4()
            if hasattr(obj, 'status') and not isinstance(obj.status, str):
                obj.status = "pending"
        db.refresh = AsyncMock(side_effect=fake_refresh)

        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artworks/{artwork.id}/suggest-artist",
                    json={"artist_name": "NewArtist"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["artist_name"] == "NewArtist"
        assert body["consensus_reached"] is False
        assert len(body["suggestions"]) == 1
        assert body["suggestions"][0]["artist_name"] == "NewArtist"
        assert body["suggestions"][0]["count"] == 1

    @pytest.mark.asyncio
    async def test_consensus_reached_at_threshold(self):
        """When 3+ users suggest the same artist, consensus is auto-accepted."""
        from types import SimpleNamespace

        user = make_user()
        artwork = _make_artwork(created_by=user.id)
        artist = _make_artist(name="Banksy")
        db = make_mock_db()

        consensus_row = SimpleNamespace(artist_id=artist.id, cnt=3)
        summary_row = SimpleNamespace(suggested_name="Banksy", cnt=3, status="accepted")

        execute_results = [
            _scalar_one_or_none(artwork),        # artwork found
            _scalar_one_or_none(None),           # no existing suggestion by user
            _scalar_one_or_none(artist),         # existing artist found
            _all([consensus_row]),                # consensus check: 3 suggestions
            MagicMock(),                          # update artist artwork_count
            MagicMock(),                          # update suggestions to accepted
            _all([summary_row]),                  # suggestion summary
        ]

        db.execute = AsyncMock(side_effect=execute_results)

        async def fake_refresh(obj):
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = uuid.uuid4()
            if hasattr(obj, 'status') and not isinstance(obj.status, str):
                obj.status = "accepted"
            elif hasattr(obj, 'status'):
                obj.status = "accepted"
        db.refresh = AsyncMock(side_effect=fake_refresh)

        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artworks/{artwork.id}/suggest-artist",
                    json={"artist_name": "Banksy"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["consensus_reached"] is True
        assert body["suggestions"][0]["status"] == "accepted"


class TestNeighborhoodEndpoints:

    @pytest.mark.asyncio
    async def test_list_neighborhoods_empty(self):
        """GET /api/neighborhoods returns empty list when no neighborhoods have artworks."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))

        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/neighborhoods")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_neighborhood_detail_not_found(self):
        """GET /api/neighborhoods/unknown returns 404."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))

        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/neighborhoods/unknown-slug")
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_neighborhoods_are_public(self):
        """Neighborhoods endpoints do not require authentication."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))

        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/neighborhoods")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
