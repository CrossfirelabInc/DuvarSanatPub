"""Tests for enhanced profile endpoints.

Covers PATCH /api/users/me extended fields, GET /api/users/:id/discoveries,
and PATCH /api/artists/:id moderator endpoint.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import Artist, Artwork, User
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


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


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


def _make_artist(artist_id=None, name="Banksy"):
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


# PATCH /api/users/me — enhanced fields


class TestUpdateProfileEnhanced:

    @pytest.mark.asyncio
    async def test_update_tagline_website_social(self):
        """PATCH /api/users/me with tagline, website, social_links."""
        user = make_user(display_name="TestUser")
        db = make_mock_db()

        async def fake_refresh(obj):
            pass

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    "/api/users/me",
                    json={
                        "tagline": "Street art lover",
                        "website": "https://example.com",
                        "social_links": {"instagram": "artfan", "twitter": "artfan"},
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        # Verify fields were set on the user object
        assert user.tagline == "Street art lover"
        assert user.website == "https://example.com"
        assert user.social_links == {"instagram": "artfan", "twitter": "artfan"}

    @pytest.mark.asyncio
    async def test_strips_at_from_social_handles(self):
        """PATCH /api/users/me strips '@' prefix from social_links values."""
        user = make_user()
        db = make_mock_db()

        async def fake_refresh(obj):
            pass

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    "/api/users/me",
                    json={
                        "social_links": {
                            "instagram": "@coolartist",
                            "twitter": "@@doublehandle",
                        },
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert user.social_links == {
            "instagram": "coolartist",
            "twitter": "doublehandle",
        }

    @pytest.mark.asyncio
    async def test_rejects_invalid_website_url(self):
        """PATCH /api/users/me rejects website that doesn't start with http(s)://."""
        user = make_user()
        db = make_mock_db()
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    "/api/users/me",
                    json={"website": "ftp://example.com"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 422


# GET /api/users/:id/discoveries


class TestUserDiscoveries:

    @pytest.mark.asyncio
    async def test_discoveries_returns_list(self):
        """GET /api/users/:id/discoveries returns artworks created by the user."""
        user = make_user()
        db = make_mock_db()

        artwork_id = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.id = artwork_id
        mock_row.title = "My Discovery"
        mock_row.status = "active"
        mock_row.photo_count = 2
        mock_row.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
        mock_row.thumbnail_url = "/uploads/thumb.jpg"

        # execute calls: 1) user existence check, 2) artworks query
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(user),
            _all([mock_row]),
        ])
        _setup_overrides(db)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/users/{user.id}/discoveries")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["title"] == "My Discovery"
        assert body[0]["photo_count"] == 2

    @pytest.mark.asyncio
    async def test_discoveries_user_not_found(self):
        """GET /api/users/:id/discoveries returns 404 for unknown user."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(f"/api/users/{uuid.uuid4()}/discoveries")
        finally:
            _clear_overrides()

        assert resp.status_code == 404


# PATCH /api/artists/:id


class TestUpdateArtist:

    @pytest.mark.asyncio
    async def test_requires_moderator_role(self):
        """PATCH /api/artists/:id with regular user returns 403."""
        user = make_user(role="user")
        db = make_mock_db()
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    f"/api/artists/{uuid.uuid4()}",
                    json={"bio": "Updated bio"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_moderator_can_update(self):
        """PATCH /api/artists/:id with moderator role updates fields."""
        user = make_user(role="moderator")
        artist = _make_artist(name="Banksy")
        db = make_mock_db()

        # execute calls: 1) artist lookup, 2) artworks query (after refresh),
        # 3) active_since query
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artist),  # artist lookup
            _all([]),  # artworks query (for response build)
            _scalar_one(None),  # active_since
        ])

        async def fake_refresh(obj):
            pass

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    f"/api/artists/{artist.id}",
                    json={
                        "bio": "Famous street artist",
                        "website": "https://banksy.co.uk",
                        "aliases": ["Robin Gunningham"],
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        # Verify fields were set on the artist object
        assert artist.bio == "Famous street artist"
        assert artist.website == "https://banksy.co.uk"
        assert artist.aliases == ["Robin Gunningham"]

    @pytest.mark.asyncio
    async def test_admin_can_update(self):
        """PATCH /api/artists/:id with admin role also works."""
        user = make_user(role="admin")
        artist = _make_artist(name="Banksy")
        db = make_mock_db()

        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artist),
            _all([]),
            _scalar_one(None),
        ])

        async def fake_refresh(obj):
            pass

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    f"/api/artists/{artist.id}",
                    json={"bio": "Admin updated"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert artist.bio == "Admin updated"

    @pytest.mark.asyncio
    async def test_artist_not_found(self):
        """PATCH /api/artists/:id returns 404 for unknown artist."""
        user = make_user(role="moderator")
        db = make_mock_db()

        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.patch(
                    f"/api/artists/{uuid.uuid4()}",
                    json={"bio": "Test"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 404
