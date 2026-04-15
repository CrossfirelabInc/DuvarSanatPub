"""Tests for follow system and leaderboard endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import Artist, Photo, User, UserFollow
from tests.conftest import make_mock_db, make_user


# Helpers


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
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


def _make_artist(artist_id=None, name="Banksy", follower_count=0):
    artist = MagicMock(spec=Artist)
    artist.id = artist_id or uuid.uuid4()
    artist.name = name
    artist.bio = None
    artist.artwork_count = 3
    artist.follower_count = follower_count
    artist.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    artist.website = None
    artist.social_links = None
    artist.verified_at = None
    artist.aliases = None
    return artist


def _make_follow(follower_id, followed_artist_id=None, followed_user_id=None):
    follow = MagicMock(spec=UserFollow)
    follow.id = uuid.uuid4()
    follow.follower_id = follower_id
    follow.followed_artist_id = followed_artist_id
    follow.followed_user_id = followed_user_id
    follow.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return follow


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


# Follow artist toggle


class TestFollowArtist:

    @pytest.mark.asyncio
    async def test_follow_artist_creates_follow(self):
        """POST /api/artists/:id/follow when not following creates follow."""
        user = make_user()
        artist = _make_artist(follower_count=0)
        db = make_mock_db()

        # 1) artist lookup, 2) existing follow check
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artist),  # artist lookup
            _scalar_one_or_none(None),    # no existing follow
            MagicMock(),                  # update follower_count
        ])

        async def fake_refresh(obj):
            if hasattr(obj, 'follower_count'):
                obj.follower_count = 1

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artists/{artist.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["following"] is True
        assert body["follower_count"] == 1

    @pytest.mark.asyncio
    async def test_unfollow_artist(self):
        """POST /api/artists/:id/follow when already following removes follow."""
        user = make_user()
        artist = _make_artist(follower_count=5)
        existing_follow = _make_follow(user.id, followed_artist_id=artist.id)
        db = make_mock_db()

        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artist),          # artist lookup
            _scalar_one_or_none(existing_follow),  # existing follow found
            MagicMock(),                           # update follower_count
        ])
        db.delete = AsyncMock()

        async def fake_refresh(obj):
            if hasattr(obj, 'follower_count'):
                obj.follower_count = 4

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artists/{artist.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["following"] is False
        assert body["follower_count"] == 4

    @pytest.mark.asyncio
    async def test_refollow_artist(self):
        """Follow -> unfollow -> re-follow cycle works."""
        user = make_user()
        artist = _make_artist(follower_count=0)
        db = make_mock_db()

        # First call: follow (no existing)
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artist),  # artist lookup
            _scalar_one_or_none(None),    # no existing follow
            MagicMock(),                  # update follower_count
        ])

        async def fake_refresh_follow(obj):
            if hasattr(obj, 'follower_count'):
                obj.follower_count = 1

        db.refresh = AsyncMock(side_effect=fake_refresh_follow)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp1 = await client.post(
                    f"/api/artists/{artist.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )

                # Second call: unfollow (existing found)
                existing_follow = _make_follow(user.id, followed_artist_id=artist.id)
                db.execute = AsyncMock(side_effect=[
                    _scalar_one_or_none(artist),
                    _scalar_one_or_none(existing_follow),
                    MagicMock(),
                ])
                db.delete = AsyncMock()

                async def fake_refresh_unfollow(obj):
                    if hasattr(obj, 'follower_count'):
                        obj.follower_count = 0

                db.refresh = AsyncMock(side_effect=fake_refresh_unfollow)

                resp2 = await client.post(
                    f"/api/artists/{artist.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )

                # Third call: re-follow
                db.execute = AsyncMock(side_effect=[
                    _scalar_one_or_none(artist),
                    _scalar_one_or_none(None),
                    MagicMock(),
                ])
                db.refresh = AsyncMock(side_effect=fake_refresh_follow)

                resp3 = await client.post(
                    f"/api/artists/{artist.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp1.json()["following"] is True
        assert resp2.json()["following"] is False
        assert resp3.json()["following"] is True

    @pytest.mark.asyncio
    async def test_follow_artist_not_found(self):
        """POST /api/artists/:id/follow returns 404 for unknown artist."""
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/artists/{uuid.uuid4()}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_follow_artist_requires_auth(self):
        """POST /api/artists/:id/follow without auth returns 401/403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(f"/api/artists/{uuid.uuid4()}/follow")
        assert resp.status_code in (401, 403)


# Follow user toggle


class TestFollowUser:

    @pytest.mark.asyncio
    async def test_follow_user(self):
        """POST /api/users/:id/follow creates a follow."""
        user = make_user()
        target = make_user(
            user_id=uuid.uuid4(),
            email="other@example.com",
            display_name="Other",
        )
        db = make_mock_db()

        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(target),  # target user lookup
            _scalar_one_or_none(None),    # no existing follow
            MagicMock(),                  # update follower_count
        ])

        async def fake_refresh(obj):
            if hasattr(obj, 'follower_count'):
                obj.follower_count = 1

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/users/{target.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["following"] is True
        assert body["follower_count"] == 1

    @pytest.mark.asyncio
    async def test_cannot_follow_yourself(self):
        """POST /api/users/:id/follow with own id returns 400."""
        user = make_user()
        db = make_mock_db()
        _setup_overrides(db, user=user)

        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/users/{user.id}/follow",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_follow_user_requires_auth(self):
        """POST /api/users/:id/follow without auth returns 401/403."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(f"/api/users/{uuid.uuid4()}/follow")
        assert resp.status_code in (401, 403)


# Leaderboard


class TestLeaderboard:

    @pytest.mark.asyncio
    async def test_leaderboard_photographers_returns_list(self):
        """GET /api/leaderboard?type=photographers returns entries."""
        db = make_mock_db()

        uid = uuid.uuid4()
        row = MagicMock()
        row.id = uid
        row.display_name = "DuvarSanat"
        row.avatar_url = None
        row.follower_count = 0
        row.score = 8

        db.execute = AsyncMock(return_value=_all([row]))
        _setup_overrides(db)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/leaderboard?type=photographers&period=all_time")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "photographers"
        assert body["period"] == "all_time"
        assert len(body["entries"]) == 1
        assert body["entries"][0]["rank"] == 1
        assert body["entries"][0]["name"] == "DuvarSanat"
        assert body["entries"][0]["score"] == 8
        assert body["entries"][0]["metric"] == "photos"

    @pytest.mark.asyncio
    async def test_leaderboard_artists_returns_list(self):
        """GET /api/leaderboard?type=artists returns entries."""
        db = make_mock_db()

        aid = uuid.uuid4()
        row = MagicMock()
        row.id = aid
        row.name = "Banksy"
        row.artwork_count = 5
        row.follower_count = 10

        db.execute = AsyncMock(return_value=_all([row]))
        _setup_overrides(db)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/leaderboard?type=artists&period=all_time")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "artists"
        assert len(body["entries"]) == 1
        assert body["entries"][0]["name"] == "Banksy"
        assert body["entries"][0]["metric"] == "artworks"

    @pytest.mark.asyncio
    async def test_leaderboard_invalid_type(self):
        """GET /api/leaderboard with invalid type returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/leaderboard?type=invalid")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_leaderboard_missing_type(self):
        """GET /api/leaderboard without type param returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/leaderboard")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_leaderboard_monthly_period(self):
        """GET /api/leaderboard?type=photographers&period=monthly is accepted."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_all([]))
        _setup_overrides(db)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/leaderboard?type=photographers&period=monthly")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["period"] == "monthly"
        assert body["entries"] == []
