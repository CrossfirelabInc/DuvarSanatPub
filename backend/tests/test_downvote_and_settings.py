"""Tests for downvote system, title suggestion, and admin settings."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token, get_current_user
from app.database import get_db
from app.main import app
from app.models import Photo, PhotoVote, SiteSetting, User
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


def _scalars_all(values):
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = values
    result.scalars.return_value = scalars
    return result


def _make_photo(photo_id=None, user_id=None, vote_count=5, downvote_count=0):
    photo = MagicMock(spec=Photo)
    photo.id = photo_id or uuid.uuid4()
    photo.user_id = user_id or uuid.uuid4()
    photo.image_url = "/uploads/test.jpg"
    photo.thumbnail_url = None
    photo.vote_count = vote_count
    photo.downvote_count = downvote_count
    photo.artwork_id = uuid.uuid4()
    photo.is_deleted = False
    photo.date_taken = None
    photo.date_uploaded = datetime(2025, 1, 1, tzinfo=timezone.utc)
    photo.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return photo


# POST /api/photos/{id}/downvote


@pytest.mark.anyio
async def test_downvote_toggle_add():
    """Authenticated user can downvote a photo they don't own."""
    user = make_user()
    photo = _make_photo()  # different user_id

    db = make_mock_db()
    # execute calls: photo lookup, existing vote check, update downvote_count
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(photo),   # photo lookup
        _scalar_one_or_none(None),    # no existing downvote
        MagicMock(),                  # update downvote_count
    ])

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.post(
            f"/api/photos/{photo.id}/downvote",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    data = res.json()
    assert data["voted"] is True


@pytest.mark.anyio
async def test_downvote_own_photo_forbidden():
    """Users cannot downvote their own photos."""
    user = make_user()
    photo = _make_photo(user_id=user.id)

    db = make_mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(photo),
    ])

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.post(
            f"/api/photos/{photo.id}/downvote",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 403


@pytest.mark.anyio
async def test_downvote_toggle_remove():
    """Downvoting again removes the downvote."""
    user = make_user()
    photo = _make_photo(downvote_count=1)

    existing_vote = MagicMock(spec=PhotoVote)
    existing_vote.id = uuid.uuid4()

    db = make_mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(photo),
        _scalar_one_or_none(existing_vote),
        MagicMock(),  # update downvote_count
    ])
    db.delete = AsyncMock()

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.post(
            f"/api/photos/{photo.id}/downvote",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    assert res.json()["voted"] is False


@pytest.mark.anyio
async def test_downvote_nonexistent_photo():
    """Downvoting a photo that doesn't exist returns 404."""
    user = make_user()
    db = make_mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(None),
    ])

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.post(
            f"/api/photos/{uuid.uuid4()}/downvote",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 404


# POST /api/photos/suggest-title


@pytest.mark.anyio
async def test_suggest_title_returns_caption():
    """Suggest-title endpoint returns a caption when model works."""
    user = make_user()

    async def _override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    with patch("app.routers.photos.clip_service") as mock_cap:
        mock_cap.is_loaded = True
        mock_cap.suggest_title.return_value = "Colorful Mural"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(user.id, user.role)
            # Create a minimal valid JPEG (just magic bytes + padding)
            jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
            res = await client.post(
                "/api/photos/suggest-title",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test.jpg", jpeg_bytes, "image/jpeg")},
            )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    assert res.json()["suggested_title"] == "Colorful Mural"


@pytest.mark.anyio
async def test_suggest_title_model_unavailable():
    """Suggest-title returns null when model is not available."""
    user = make_user()

    async def _override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    with patch("app.routers.photos.clip_service") as mock_cap:
        mock_cap.is_loaded = True
        mock_cap.suggest_title.return_value = None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            token = create_access_token(user.id, user.role)
            jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
            res = await client.post(
                "/api/photos/suggest-title",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test.jpg", jpeg_bytes, "image/jpeg")},
            )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    assert res.json()["suggested_title"] is None


# GET /api/settings (public)


@pytest.mark.anyio
async def test_get_public_settings():
    """Public settings endpoint returns feature flags."""
    settings = [
        MagicMock(key="dm_enabled", value="true"),
        MagicMock(key="tours_enabled", value="false"),
    ]

    db = make_mock_db()
    db.execute = AsyncMock(return_value=_scalars_all(settings))

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/settings")

    app.dependency_overrides.pop(get_db, None)

    assert res.status_code == 200
    data = res.json()
    assert data["dm_enabled"] is True
    assert data["tours_enabled"] is False


# GET /api/admin/settings (admin only)


@pytest.mark.anyio
async def test_admin_settings_requires_admin():
    """Non-admin users cannot access admin settings."""
    user = make_user(role="user")

    async def _override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.get(
            "/api/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 403


@pytest.mark.anyio
async def test_admin_settings_success():
    """Admin user can get all settings."""
    user = make_user(role="admin")
    setting = MagicMock(spec=SiteSetting)
    setting.key = "dm_enabled"
    setting.value = "true"
    setting.updated_by = None
    setting.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)

    db = make_mock_db()
    db.execute = AsyncMock(return_value=_scalars_all([setting]))

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.get(
            "/api/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert any(d["key"] == "dm_enabled" for d in data)


# PUT /api/admin/settings


@pytest.mark.anyio
async def test_update_settings_requires_admin():
    """Non-admin users cannot update settings."""
    user = make_user(role="moderator")

    async def _override_db():
        yield make_mock_db()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.put(
            "/api/admin/settings",
            json={"dm_enabled": "false"},
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 403


@pytest.mark.anyio
async def test_update_settings_success():
    """Admin can update a feature toggle."""
    user = make_user(role="admin")
    setting = MagicMock(spec=SiteSetting)
    setting.key = "dm_enabled"
    setting.value = "true"
    setting.updated_by = None
    setting.updated_at = None

    db = make_mock_db()
    db.execute = AsyncMock(return_value=_scalar_one_or_none(setting))

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = create_access_token(user.id, user.role)
        res = await client.put(
            "/api/admin/settings",
            json={"dm_enabled": "false"},
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    assert res.json()["dm_enabled"] == "false"
