"""Tests for comments, voting, favorites, and search endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    Artist,
    Artwork,
    Comment,
    Photo,
    PhotoVote,
    User,
    UserFavorite,
)
from tests.conftest import make_mock_db, make_user


# Helpers


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _all(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _make_comment(
    user_id: uuid.UUID,
    target_type: str = "artwork",
    target_id: uuid.UUID | None = None,
    comment_id: uuid.UUID | None = None,
    content: str = "Nice mural!",
    is_deleted: bool = False,
) -> MagicMock:
    comment = MagicMock(spec=Comment)
    comment.id = comment_id or uuid.uuid4()
    comment.target_type = target_type
    comment.target_id = target_id or uuid.uuid4()
    comment.user_id = user_id
    comment.content = content
    comment.is_deleted = is_deleted
    comment.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    comment.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return comment


def _make_artwork(
    created_by: uuid.UUID,
    artwork_id: uuid.UUID | None = None,
) -> MagicMock:
    aw = MagicMock(spec=Artwork)
    aw.id = artwork_id or uuid.uuid4()
    aw.title = "Test Mural"
    aw.description = "A test artwork"
    aw.location = None
    aw.artist_id = None
    aw.status = "active"
    aw.created_by = created_by
    aw.photo_count = 1
    aw.created_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    aw.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return aw


def _make_photo(
    user_id: uuid.UUID,
    photo_id: uuid.UUID | None = None,
    artwork_id: uuid.UUID | None = None,
) -> MagicMock:
    photo = MagicMock(spec=Photo)
    photo.id = photo_id or uuid.uuid4()
    photo.user_id = user_id
    photo.artwork_id = artwork_id
    photo.image_url = "/uploads/test.jpg"
    photo.vote_count = 0
    photo.date_taken = None
    photo.date_uploaded = datetime(2025, 6, 1, tzinfo=timezone.utc)
    photo.image_embedding = None
    return photo


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


# Comments


class TestCreateComment:

    @pytest.mark.asyncio
    async def test_create_comment_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/api/comments", json={
                "target_type": "artwork",
                "target_id": str(uuid.uuid4()),
                "content": "Hello",
            })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_comment_invalid_target_type(self):
        user = make_user()
        db = make_mock_db()
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/comments",
                    json={
                        "target_type": "photo",
                        "target_id": str(uuid.uuid4()),
                        "content": "Hello",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_comment_target_not_found(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/comments",
                    json={
                        "target_type": "artwork",
                        "target_id": str(uuid.uuid4()),
                        "content": "Hello",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_comment_success(self):
        user = make_user()
        artwork = _make_artwork(user.id)
        db = make_mock_db()

        comment_id = uuid.uuid4()
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        # First call: target lookup; then commit + refresh
        db.execute = AsyncMock(return_value=_scalar_one_or_none(artwork))

        async def fake_refresh(obj):
            obj.id = comment_id
            obj.created_at = now

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/comments",
                    json={
                        "target_type": "artwork",
                        "target_id": str(artwork.id),
                        "content": "Great work!",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 201
        body = resp.json()
        assert body["content"] == "Great work!"
        assert body["user_display_name"] == user.display_name
        assert body["target_type"] == "artwork"


class TestListComments:

    @pytest.mark.asyncio
    async def test_list_comments_public(self):
        """GET /api/comments is public."""
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_all([]))
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(
                    f"/api/comments?target_type=artwork&target_id={uuid.uuid4()}"
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_comments_invalid_target_type(self):
        """Invalid target_type returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                f"/api/comments?target_type=photo&target_id={uuid.uuid4()}"
            )
        assert resp.status_code == 422


class TestDeleteComment:

    @pytest.mark.asyncio
    async def test_delete_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.delete(f"/api/comments/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.delete(
                    f"/api/comments/{uuid.uuid4()}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_forbidden_other_user(self):
        user = make_user()
        other_user_id = uuid.uuid4()
        comment = _make_comment(user_id=other_user_id)
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(comment))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.delete(
                    f"/api/comments/{comment.id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_own_comment_success(self):
        user = make_user()
        comment = _make_comment(user_id=user.id)
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(comment))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.delete(
                    f"/api/comments/{comment.id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_moderator_can_delete_others_comment(self):
        mod = make_user(role="moderator")
        other_user_id = uuid.uuid4()
        comment = _make_comment(user_id=other_user_id)
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(comment))
        _setup_overrides(db, user=mod)
        try:
            token = create_access_token(mod.id, mod.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.delete(
                    f"/api/comments/{comment.id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 204


# Voting


class TestPhotoVote:

    @pytest.mark.asyncio
    async def test_vote_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(f"/api/photos/{uuid.uuid4()}/vote")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_vote_photo_not_found(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/photos/{uuid.uuid4()}/vote",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_vote_own_photo_forbidden(self):
        user = make_user()
        photo = _make_photo(user_id=user.id)
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(photo))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/photos/{photo.id}/vote",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 403
        assert "own photos" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_vote_create_new_vote(self):
        user = make_user()
        other_user_id = uuid.uuid4()
        photo = _make_photo(user_id=other_user_id)
        db = make_mock_db()

        # First call: photo lookup; second: existing vote check
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(photo),   # photo lookup
            _scalar_one_or_none(None),    # no existing vote
            MagicMock(),                  # update photo
            MagicMock(),                  # update user
        ])

        async def fake_refresh(obj):
            obj.vote_count = 1

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/photos/{photo.id}/vote",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["voted"] is True
        assert body["vote_count"] == 1

    @pytest.mark.asyncio
    async def test_vote_toggle_remove(self):
        user = make_user()
        other_user_id = uuid.uuid4()
        photo = _make_photo(user_id=other_user_id)
        photo.vote_count = 1
        existing_vote = MagicMock(spec=PhotoVote)
        db = make_mock_db()

        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(photo),          # photo lookup
            _scalar_one_or_none(existing_vote),  # existing vote found
            MagicMock(),                         # update photo
            MagicMock(),                         # update user
        ])
        db.delete = AsyncMock()

        async def fake_refresh(obj):
            obj.vote_count = 0

        db.refresh = AsyncMock(side_effect=fake_refresh)
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/photos/{photo.id}/vote",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["voted"] is False
        assert body["vote_count"] == 0


# Favorites


class TestFavoriteToggle:

    @pytest.mark.asyncio
    async def test_favorite_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(f"/api/favorites/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_favorite_artwork_not_found(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_scalar_one_or_none(None))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/favorites/{uuid.uuid4()}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_favorite_add(self):
        user = make_user()
        artwork = _make_artwork(user.id)
        db = make_mock_db()

        # First call: artwork lookup; second: existing favorite check
        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artwork),   # artwork exists
            _scalar_one_or_none(None),      # no existing favorite
        ])
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/favorites/{artwork.id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["favorited"] is True

    @pytest.mark.asyncio
    async def test_favorite_remove(self):
        user = make_user()
        artwork = _make_artwork(user.id)
        existing_fav = MagicMock(spec=UserFavorite)
        db = make_mock_db()

        db.execute = AsyncMock(side_effect=[
            _scalar_one_or_none(artwork),       # artwork exists
            _scalar_one_or_none(existing_fav),  # existing favorite
        ])
        db.delete = AsyncMock()
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    f"/api/favorites/{artwork.id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json()["favorited"] is False


class TestListFavorites:

    @pytest.mark.asyncio
    async def test_list_favorites_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/favorites")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_favorites_empty(self):
        user = make_user()
        db = make_mock_db()
        db.execute = AsyncMock(return_value=_all([]))
        _setup_overrides(db, user=user)
        try:
            token = create_access_token(user.id, user.role)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(
                    "/api/favorites",
                    headers={"Authorization": f"Bearer {token}"},
                )
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        assert resp.json() == []


# Search


class TestSearch:

    @pytest.mark.asyncio
    async def test_search_is_public(self):
        """GET /api/search is public."""
        db = make_mock_db()
        # Two execute calls: artworks + artists
        db.execute = AsyncMock(side_effect=[_all([]), _all([])])
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/search?q=mural")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert "artworks" in body
        assert "artists" in body

    @pytest.mark.asyncio
    async def test_search_requires_query(self):
        """Missing q parameter returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/search")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_artworks_only(self):
        db = make_mock_db()
        # Only artworks search, no artists
        db.execute = AsyncMock(return_value=_all([]))
        _setup_overrides(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get("/api/search?q=mural&type=artworks")
        finally:
            _clear_overrides()

        assert resp.status_code == 200
        body = resp.json()
        assert body["artworks"] == []
        assert body["artists"] == []

    @pytest.mark.asyncio
    async def test_search_invalid_type(self):
        """Invalid type parameter returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/search?q=mural&type=photos")
        assert resp.status_code == 422
